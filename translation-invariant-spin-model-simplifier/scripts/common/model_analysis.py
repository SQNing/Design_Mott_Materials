"""Generic downstream analyses for normalized/simplified models."""

import ast
from collections.abc import Mapping
from itertools import product
import math
import operator
import re

import numpy as np

from classical.lt_fourier_exchange import fourier_exchange_matrix
from common.hamiltonian_symmetry_gate import require_current_symmetry_stamp


_SCALAR_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_SCALAR_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_SCALAR_FUNCTIONS = {
    "abs": abs,
    "cos": math.cos,
    "cosh": math.cosh,
    "exp": math.exp,
    "log": math.log,
    "sin": math.sin,
    "sinh": math.sinh,
    "sqrt": math.sqrt,
    "tan": math.tan,
    "tanh": math.tanh,
}


def _evaluate_scalar_expression(node, values):
    if isinstance(node, ast.Expression):
        return _evaluate_scalar_expression(node.body, values)
    if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
        return float(node.value)
    if isinstance(node, ast.Name) and node.id in values:
        return float(values[node.id])
    if type(node) is ast.BinOp and type(node.op) in _SCALAR_BINARY_OPERATORS:
        return _SCALAR_BINARY_OPERATORS[type(node.op)](
            _evaluate_scalar_expression(node.left, values),
            _evaluate_scalar_expression(node.right, values),
        )
    if type(node) is ast.UnaryOp and type(node.op) in _SCALAR_UNARY_OPERATORS:
        return _SCALAR_UNARY_OPERATORS[type(node.op)](
            _evaluate_scalar_expression(node.operand, values)
        )
    if (
        type(node) is ast.Call
        and type(node.func) is ast.Name
        and node.func.id in _SCALAR_FUNCTIONS
        and len(node.args) == 1
        and not node.keywords
    ):
        return _SCALAR_FUNCTIONS[node.func.id](
            _evaluate_scalar_expression(node.args[0], values)
        )
    raise ValueError("unsupported scalar equation expression")


def _scalar_root(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "scalar_root",
            "blocker": "model simplification did not complete",
        }
    variable = request.get("variable")
    equation = request.get("equation")
    parameters = request.get("parameters", {})
    bracket = request.get("bracket")
    tolerance = request.get("absolute_tolerance", 1.0e-10)
    if (
        not isinstance(variable, str)
        or not variable.isidentifier()
        or not isinstance(equation, str)
        or not equation.strip()
        or not isinstance(parameters, Mapping)
        or not isinstance(bracket, (tuple, list))
        or len(bracket) != 2
        or isinstance(tolerance, bool)
        or not isinstance(tolerance, (int, float))
        or not math.isfinite(float(tolerance))
        or float(tolerance) <= 0.0
    ):
        return {
            "status": "invalid_request",
            "task": "scalar_root",
            "blocker": "scalar_root requires an equation, variable, bracket, and positive tolerance",
        }
    try:
        values = {
            str(name): float(value) for name, value in parameters.items()
        }
        if variable in values or any(
            not name.isidentifier() or not math.isfinite(value)
            for name, value in values.items()
        ):
            raise ValueError("invalid scalar parameter")
        lower, upper = (float(bracket[0]), float(bracket[1]))
        if not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper:
            raise ValueError("invalid scalar bracket")
        tree = ast.parse(equation, mode="eval")

        def evaluate(point):
            result = float(
                _evaluate_scalar_expression(
                    tree, {**values, variable: point}
                )
            )
            if not math.isfinite(result):
                raise ValueError("non-finite scalar equation value")
            return result

        lower_value = evaluate(lower)
        upper_value = evaluate(upper)
    except (ArithmeticError, TypeError, ValueError, SyntaxError) as exc:
        return {
            "status": "invalid_request",
            "task": "scalar_root",
            "blocker": str(exc),
        }
    if lower_value == 0.0:
        root, residual, width = lower, 0.0, 0.0
    elif upper_value == 0.0:
        root, residual, width = upper, 0.0, 0.0
    elif lower_value * upper_value > 0.0:
        return {
            "status": "not_bracketed",
            "task": "scalar_root",
            "blocker": "equation has the same sign at both bracket endpoints",
        }
    else:
        root = 0.5 * (lower + upper)
        residual = abs(evaluate(root))
        for _iteration in range(256):
            root = 0.5 * (lower + upper)
            root_value = evaluate(root)
            residual = abs(root_value)
            if residual <= float(tolerance) and (
                upper - lower
            ) <= 2.0 * float(tolerance):
                break
            if lower_value * root_value <= 0.0:
                upper = root
                upper_value = root_value
            else:
                lower = root
                lower_value = root_value
        width = upper - lower
        if residual > float(tolerance):
            return {
                "status": "not_converged",
                "task": "scalar_root",
                "blocker": "bisection did not reach the requested residual",
            }
    result = {
        "status": "ok",
        "task": "scalar_root",
        "observable": request.get("observable", variable),
        "units": request.get("units", "dimensionless"),
        "value": float(root),
        "residual": float(residual),
        "bracket_width": float(width),
    }
    return result


def _local_spectrum(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "local_spectrum",
            "blocker": "model simplification did not complete",
        }
    local_term_record = product_result.get("local_term_record")
    representation = (
        local_term_record.get("representation", {})
        if isinstance(local_term_record, Mapping)
        else {}
    )
    if representation.get("kind") != "matrix":
        return {
            "status": "unsupported",
            "task": "local_spectrum",
            "blocker": "the model has no compiled local matrix",
        }

    matrix = np.asarray(representation.get("value"), dtype=complex)
    if (
        matrix.ndim != 2
        or matrix.shape[0] != matrix.shape[1]
        or matrix.shape[0] == 0
        or not np.all(np.isfinite(matrix))
    ):
        return {
            "status": "invalid_model",
            "task": "local_spectrum",
            "blocker": "the compiled local matrix is not finite and square",
        }
    if not np.allclose(matrix, matrix.conj().T, atol=1.0e-12, rtol=0.0):
        return {
            "status": "invalid_model",
            "task": "local_spectrum",
            "blocker": "the compiled local matrix is not Hermitian",
        }

    eigenvalues = np.linalg.eigvalsh(matrix).real
    ground_energy = float(eigenvalues[0])
    level_tolerance = 1.0e-10
    ground_state_degeneracy = int(
        np.count_nonzero(
            np.isclose(
                eigenvalues,
                ground_energy,
                atol=level_tolerance,
                rtol=0.0,
            )
        )
    )
    excited = eigenvalues[ground_state_degeneracy:]
    spectral_gap = (
        float(excited[0] - ground_energy) if len(excited) else 0.0
    )
    observable = request.get("observable", "eigenvalues")
    if observable == "spectral_gap":
        value = spectral_gap
    elif observable == "ground_state_energy":
        value = ground_energy
    elif observable == "ground_state_degeneracy":
        value = ground_state_degeneracy
    else:
        value = [float(item) for item in eigenvalues]
    return {
        "status": "ok",
        "task": "local_spectrum",
        "observable": observable,
        "value": value,
        "units": request.get("units", "model_energy_units"),
        "matrix_dimension": int(matrix.shape[0]),
        "eigenvalues": [float(value) for value in eigenvalues],
        "ground_state_energy": ground_energy,
        "ground_state_degeneracy": ground_state_degeneracy,
        "spectral_gap": spectral_gap,
    }


def _spin_one_bilinear_biquadratic_decomposition(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "spin_one_bilinear_biquadratic_decomposition",
            "blocker": "model simplification did not complete",
        }
    local_term_record = product_result.get("local_term_record")
    representation = (
        local_term_record.get("representation", {})
        if isinstance(local_term_record, Mapping)
        else {}
    )
    matrix = np.asarray(representation.get("value"), dtype=complex)
    if (
        representation.get("kind") != "matrix"
        or matrix.shape != (9, 9)
        or local_term_record.get("support") != [0, 1]
        or not np.all(np.isfinite(matrix))
        or not np.allclose(matrix, matrix.conj().T, atol=1.0e-12, rtol=0.0)
    ):
        return {
            "status": "unsupported",
            "task": "spin_one_bilinear_biquadratic_decomposition",
            "blocker": "analysis requires a Hermitian two-spin-one matrix",
        }

    root_two = math.sqrt(2.0)
    spin_x = np.asarray(
        [
            [0.0, 1.0 / root_two, 0.0],
            [1.0 / root_two, 0.0, 1.0 / root_two],
            [0.0, 1.0 / root_two, 0.0],
        ],
        dtype=complex,
    )
    spin_y = np.asarray(
        [
            [0.0, -1.0j / root_two, 0.0],
            [1.0j / root_two, 0.0, -1.0j / root_two],
            [0.0, 1.0j / root_two, 0.0],
        ],
        dtype=complex,
    )
    spin_z = np.diag([1.0, 0.0, -1.0]).astype(complex)
    dot_product = sum(
        np.kron(component, component)
        for component in (spin_x, spin_y, spin_z)
    )
    basis = (np.eye(9, dtype=complex), dot_product, dot_product @ dot_product)
    design = np.column_stack([item.reshape(-1) for item in basis])
    coefficients, _residuals, rank, _singular_values = np.linalg.lstsq(
        design, matrix.reshape(-1), rcond=None
    )
    reconstructed = sum(
        coefficient * basis_matrix
        for coefficient, basis_matrix in zip(coefficients, basis)
    )
    scale = max(1.0, float(np.linalg.norm(matrix)))
    residual = float(np.linalg.norm(matrix - reconstructed) / scale)
    if rank != 3 or residual > 1.0e-10 or np.max(np.abs(coefficients.imag)) > 1.0e-10:
        return {
            "status": "unsupported",
            "task": "spin_one_bilinear_biquadratic_decomposition",
            "blocker": "matrix is not an isotropic bilinear-biquadratic spin-one bond",
            "reconstruction_residual": residual,
        }
    constant_shift, bilinear, biquadratic = (
        float(value.real) for value in coefficients
    )
    if abs(bilinear) <= 1.0e-14:
        return {
            "status": "unsupported",
            "task": "spin_one_bilinear_biquadratic_decomposition",
            "blocker": "the bilinear coefficient is zero",
        }
    ratio = biquadratic / bilinear
    theta = math.atan2(biquadratic, bilinear)
    su3_symmetric = abs(bilinear - biquadratic) <= 1.0e-10 * max(
        1.0, abs(bilinear), abs(biquadratic)
    )
    value = {
        "bilinear_biquadratic_ratio": ratio,
        "theta_radians": theta,
        "su3_symmetric": su3_symmetric,
    }
    return {
        "status": "ok",
        "task": "spin_one_bilinear_biquadratic_decomposition",
        "observable": request.get("observable", "coefficient_summary"),
        "units": request.get("units", "model_energy_units"),
        "value": value,
        "constant_shift": constant_shift,
        "bilinear_coefficient": bilinear,
        "biquadratic_coefficient": biquadratic,
        "bilinear_biquadratic_ratio": ratio,
        "theta_radians": theta,
        "su3_symmetric": su3_symmetric,
        "reconstruction_residual": residual,
    }


def _one_dimensional_transfer_matrix(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "one_dimensional_transfer_matrix",
            "blocker": "model simplification did not complete",
        }
    lattice = product_result.get("lattice", {})
    lattice_structure = product_result.get("normalized_model", {}).get(
        "lattice_structure", {}
    )
    record = product_result.get("local_term_record", {})
    representation = record.get("representation", {})
    local_basis = record.get("local_basis_order", [])
    local_dimension = len(local_basis)
    matrix = np.asarray(representation.get("value"), dtype=complex)
    if (
        lattice.get("kind") != "chain"
        or lattice.get("dimension") != 1
        or len(lattice_structure.get("basis_sites", [])) != 1
        or len(record.get("support", [])) != 2
        or local_dimension < 2
        or representation.get("kind") != "matrix"
        or matrix.shape != (local_dimension**2, local_dimension**2)
        or not np.all(np.isfinite(matrix))
    ):
        return {
            "status": "unsupported",
            "task": "one_dimensional_transfer_matrix",
            "blocker": "analysis requires a one-site finite-state chain with one finite pair matrix",
        }
    diagonal = np.diag(np.diag(matrix))
    if not np.allclose(matrix, diagonal, atol=1.0e-12, rtol=0.0):
        return {
            "status": "unsupported",
            "task": "one_dimensional_transfer_matrix",
            "blocker": "pair Hamiltonian is not diagonal in the declared local basis",
        }
    energies = np.diag(matrix).real.reshape(
        (local_dimension, local_dimension)
    )
    if (
        not np.allclose(np.diag(matrix).imag, 0.0, atol=1.0e-12, rtol=0.0)
        or not np.allclose(energies, energies.T, atol=1.0e-12, rtol=0.0)
    ):
        return {
            "status": "unsupported",
            "task": "one_dimensional_transfer_matrix",
            "blocker": "pair energies must be real and symmetric",
        }
    temperatures = request.get(
        "diagnostic_temperatures", [0.5, 1.0, 2.0]
    )
    if not isinstance(temperatures, (tuple, list)) or not temperatures:
        return {
            "status": "invalid_request",
            "task": "one_dimensional_transfer_matrix",
            "blocker": "diagnostic_temperatures must be a nonempty list",
        }
    diagnostics = []
    for raw_temperature in temperatures:
        try:
            temperature = float(raw_temperature)
        except (TypeError, ValueError):
            temperature = math.nan
        if not math.isfinite(temperature) or temperature <= 0.0:
            return {
                "status": "invalid_request",
                "task": "one_dimensional_transfer_matrix",
                "blocker": "diagnostic temperatures must be finite and positive",
            }
        shifted = energies - float(np.min(energies))
        transfer = np.exp(-shifted / temperature)
        eigenvalues = np.linalg.eigvalsh(transfer)
        largest = float(eigenvalues[-1])
        subleading_magnitude = max(
            (abs(float(value)) for value in eigenvalues[:-1]),
            default=0.0,
        )
        diagnostics.append(
            {
                "temperature": temperature,
                "largest_eigenvalue": largest,
                "spectral_gap": largest - subleading_magnitude,
            }
        )
    return {
        "status": "ok",
        "task": "one_dimensional_transfer_matrix",
        "observable": request.get("observable", "critical_temperature"),
        "units": request.get("units", "model_energy_units/k_B"),
        "value": 0.0,
        "finite_temperature_transition": False,
        "proof_kind": "positive_finite_transfer_matrix",
        "local_state_count": local_dimension,
        "diagnostics": diagnostics,
    }


def _classical_sz_enumeration(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "classical_sz_enumeration",
            "blocker": "model simplification did not complete",
        }
    canonical = product_result.get("canonical_model", {})
    parsed_terms = []
    sites = set()
    for body_kind in (
        "one_body",
        "two_body",
        "three_body",
        "four_body",
        "higher_body",
    ):
        for term in canonical.get(body_kind, []):
            factors = []
            for token in str(term.get("canonical_label", "")).split():
                match = re.fullmatch(r"Sz@(?P<site>\d+)", token)
                if match is None:
                    return {
                        "status": "unsupported",
                        "task": "classical_sz_enumeration",
                        "blocker": "enumeration supports only products of Sz operators",
                    }
                site = int(match.group("site"))
                sites.add(site)
                factors.append(site)
            try:
                coefficient = complex(term.get("coefficient", 0.0))
            except (TypeError, ValueError):
                coefficient = complex(math.nan, math.nan)
            if (
                not factors
                or not math.isfinite(coefficient.real)
                or not math.isfinite(coefficient.imag)
                or abs(coefficient.imag) > 1.0e-12
            ):
                return {
                    "status": "unsupported",
                    "task": "classical_sz_enumeration",
                    "blocker": "enumeration requires finite real Sz coefficients",
                }
            parsed_terms.append((float(coefficient.real), tuple(factors)))
    if not parsed_terms or not sites or len(sites) > 20:
        return {
            "status": "unsupported",
            "task": "classical_sz_enumeration",
            "blocker": "enumeration requires between 1 and 20 active sites",
        }
    ordered_sites = sorted(sites)
    site_positions = {
        site: position for position, site in enumerate(ordered_sites)
    }
    degeneracy_by_energy = {}
    for configuration in product((-0.5, 0.5), repeat=len(ordered_sites)):
        energy = 0.0
        for coefficient, factors in parsed_terms:
            factor_value = 1.0
            for site in factors:
                factor_value *= configuration[site_positions[site]]
            energy += coefficient * factor_value
        canonical_energy = float(round(energy, 12))
        degeneracy_by_energy[canonical_energy] = (
            degeneracy_by_energy.get(canonical_energy, 0) + 1
        )
    levels = [
        {"energy": energy, "degeneracy": degeneracy_by_energy[energy]}
        for energy in sorted(degeneracy_by_energy)
    ]
    return {
        "status": "ok",
        "task": "classical_sz_enumeration",
        "observable": request.get("observable", "energy_levels"),
        "units": request.get("units", "model_energy_units"),
        "value": levels,
        "configuration_count": 2 ** len(ordered_sites),
        "ground_state_energy": levels[0]["energy"],
        "ground_state_degeneracy": levels[0]["degeneracy"],
    }


def _local_constraint_entropy_estimate(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "local_constraint_entropy_estimate",
            "blocker": "model simplification did not complete",
        }
    canonical = product_result.get("canonical_model", {})
    two_body = canonical.get("two_body", [])
    structure = product_result.get("normalized_model", {}).get(
        "lattice_structure", {}
    )
    orbit_ref = request.get("bond_orbit_ref")
    orbits = [
        orbit
        for orbit in structure.get("bond_orbits", [])
        if orbit.get("orbit_ref") == orbit_ref
    ]
    try:
        constraints_per_site = float(request.get("constraints_per_site"))
        coefficient = float(two_body[0].get("coefficient"))
    except (IndexError, TypeError, ValueError):
        constraints_per_site = math.nan
        coefficient = math.nan
    if (
        len(two_body) != 1
        or two_body[0].get("canonical_label") != "Sz@0 Sz@1"
        or len(orbits) != 1
        or not math.isfinite(coefficient)
        or not math.isfinite(constraints_per_site)
        or constraints_per_site <= 0.0
    ):
        return {
            "status": "unsupported",
            "task": "local_constraint_entropy_estimate",
            "blocker": "analysis requires one binary Sz constraint orbit",
        }
    site_count = len(structure.get("basis_sites", []))
    members = orbits[0].get("members", [])
    bonds = []
    for member in members:
        source = member.get("source")
        target = member.get("target")
        if (
            isinstance(source, bool)
            or not isinstance(source, int)
            or isinstance(target, bool)
            or not isinstance(target, int)
            or not 0 <= source < site_count
            or not 0 <= target < site_count
            or list(member.get("translation", [])) != [0, 0, 0]
        ):
            return {
                "status": "unsupported",
                "task": "local_constraint_entropy_estimate",
                "blocker": "constraint members must lie in one finite cell",
            }
        bonds.append((source, target))
    if not bonds or site_count < 1 or site_count > 20:
        return {
            "status": "unsupported",
            "task": "local_constraint_entropy_estimate",
            "blocker": "constraint cell must contain 1 to 20 sites",
        }
    energies = []
    for configuration in product((-0.5, 0.5), repeat=site_count):
        energies.append(
            coefficient
            * math.fsum(
                configuration[source] * configuration[target]
                for source, target in bonds
            )
        )
    ground_energy = min(energies)
    allowed_count = sum(
        abs(energy - ground_energy) <= 1.0e-12 for energy in energies
    )
    configuration_count = 2**site_count
    entropy = math.log(2.0) + constraints_per_site * math.log(
        allowed_count / configuration_count
    )
    return {
        "status": "ok",
        "task": "local_constraint_entropy_estimate",
        "observable": request.get(
            "observable", "constraint_entropy_per_site"
        ),
        "units": request.get("units", "k_B/site"),
        "value": entropy,
        "site_count": site_count,
        "configuration_count": configuration_count,
        "allowed_configuration_count": allowed_count,
        "ground_state_energy": ground_energy,
        "constraints_per_site": constraints_per_site,
    }


def _periodic_classical_sz_enumeration(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "periodic_classical_sz_enumeration",
            "blocker": "model simplification did not complete",
        }

    canonical = product_result.get("canonical_model", {})
    two_body = canonical.get("two_body", [])
    if (
        len(two_body) != 1
        or two_body[0].get("canonical_label") != "Sz@0 Sz@1"
        or any(
            canonical.get(body_kind, [])
            for body_kind in (
                "one_body",
                "three_body",
                "four_body",
                "higher_body",
            )
        )
    ):
        return {
            "status": "unsupported",
            "task": "periodic_classical_sz_enumeration",
            "blocker": (
                "periodic enumeration currently requires one Sz@0 Sz@1 "
                "bond term and no other canonical terms"
            ),
        }
    try:
        coefficient = complex(two_body[0].get("coefficient"))
    except (TypeError, ValueError):
        coefficient = complex(math.nan, math.nan)
    if (
        not math.isfinite(coefficient.real)
        or not math.isfinite(coefficient.imag)
        or abs(coefficient.imag) > 1.0e-12
    ):
        return {
            "status": "unsupported",
            "task": "periodic_classical_sz_enumeration",
            "blocker": "periodic enumeration requires a finite real bond coefficient",
        }

    normalized = product_result.get("normalized_model", {})
    lattice = normalized.get("lattice", {})
    lattice_structure = normalized.get("lattice_structure", {})
    try:
        dimension = int(
            lattice.get("dimension", lattice_structure.get("dimension"))
        )
    except (TypeError, ValueError):
        dimension = 0
    basis_sites = lattice_structure.get("basis_sites", [])
    orbit_ref = request.get("bond_orbit_ref")
    matching_orbits = [
        orbit
        for orbit in lattice_structure.get("bond_orbits", [])
        if isinstance(orbit, Mapping)
        and orbit.get("orbit_ref") == orbit_ref
    ]
    supercells = request.get("supercells")
    if (
        dimension not in {1, 2, 3}
        or not isinstance(basis_sites, (tuple, list))
        or not basis_sites
        or len(matching_orbits) != 1
        or not isinstance(supercells, (tuple, list))
        or not supercells
    ):
        return {
            "status": "invalid_request",
            "task": "periodic_classical_sz_enumeration",
            "blocker": (
                "analysis requires a periodic lattice, one selected bond "
                "orbit, and at least one supercell"
            ),
        }

    members = matching_orbits[0].get("members", [])
    estimates = []
    basis_count = len(basis_sites)
    for shape_value in supercells:
        if (
            not isinstance(shape_value, (tuple, list))
            or len(shape_value) != dimension
            or any(
                isinstance(length, bool)
                or not isinstance(length, int)
                or length <= 0
                for length in shape_value
            )
        ):
            return {
                "status": "invalid_request",
                "task": "periodic_classical_sz_enumeration",
                "blocker": "each supercell must contain one positive integer per lattice dimension",
            }
        shape = tuple(int(length) for length in shape_value)
        cells = list(product(*(range(length) for length in shape)))
        site_count = len(cells) * basis_count
        if site_count > 20:
            return {
                "status": "unsupported",
                "task": "periodic_classical_sz_enumeration",
                "blocker": "periodic enumeration is limited to 20 sites",
            }
        site_index = {
            (cell, basis): cell_index * basis_count + basis
            for cell_index, cell in enumerate(cells)
            for basis in range(basis_count)
        }
        edges = []
        for cell in cells:
            for member in members:
                if not isinstance(member, Mapping):
                    return {
                        "status": "invalid_model",
                        "task": "periodic_classical_sz_enumeration",
                        "blocker": "bond-orbit members must be mappings",
                    }
                source = member.get("source")
                target = member.get("target")
                translation = member.get("translation")
                if (
                    isinstance(source, bool)
                    or not isinstance(source, int)
                    or isinstance(target, bool)
                    or not isinstance(target, int)
                    or source < 0
                    or source >= basis_count
                    or target < 0
                    or target >= basis_count
                    or not isinstance(translation, (tuple, list))
                    or len(translation) < dimension
                    or any(
                        isinstance(value, bool) or not isinstance(value, int)
                        for value in translation[:dimension]
                    )
                ):
                    return {
                        "status": "invalid_model",
                        "task": "periodic_classical_sz_enumeration",
                        "blocker": "bond-orbit member indices or translation are invalid",
                    }
                target_cell = tuple(
                    (cell[axis] + translation[axis]) % shape[axis]
                    for axis in range(dimension)
                )
                edges.append(
                    (
                        site_index[(cell, source)],
                        site_index[(target_cell, target)],
                    )
                )
        if not edges:
            return {
                "status": "invalid_model",
                "task": "periodic_classical_sz_enumeration",
                "blocker": "selected bond orbit has no members",
            }

        ground_energy = None
        ground_degeneracy = 0
        bond_scale = float(coefficient.real) / 4.0
        for mask in range(1 << site_count):
            energy = 0.0
            for left, right in edges:
                left_spin = 1 if mask & (1 << left) else -1
                right_spin = 1 if mask & (1 << right) else -1
                energy += bond_scale * left_spin * right_spin
            energy = float(round(energy, 12))
            if ground_energy is None or energy < ground_energy:
                ground_energy = energy
                ground_degeneracy = 1
            elif energy == ground_energy:
                ground_degeneracy += 1
        estimates.append(
            {
                "supercell": list(shape),
                "site_count": site_count,
                "bond_count": len(edges),
                "ground_state_energy": ground_energy,
                "ground_state_degeneracy": ground_degeneracy,
                "entropy_per_site": math.log(ground_degeneracy) / site_count,
            }
        )

    final = estimates[-1]
    result = {
        "status": "ok",
        "task": "periodic_classical_sz_enumeration",
        "observable": request.get(
            "observable", "finite_size_residual_entropy"
        ),
        "units": request.get("units", "k_B/spin"),
        "value": final["entropy_per_site"],
        "ground_state_energy": final["ground_state_energy"],
        "ground_state_degeneracy": final["ground_state_degeneracy"],
        "finite_size_estimates": estimates,
    }
    if request.get("require_thermodynamic_limit") is True:
        result["status"] = "inconclusive"
        result["blocker"] = (
            "finite periodic clusters do not yet certify the thermodynamic-limit entropy"
        )
    return result


def _spin_matrices(local_dimension):
    spin = 0.5 * (local_dimension - 1)
    magnetic_values = [spin - index for index in range(local_dimension)]
    raising = np.zeros((local_dimension, local_dimension), dtype=complex)
    lowering = np.zeros((local_dimension, local_dimension), dtype=complex)
    for index, magnetic_value in enumerate(magnetic_values):
        if index > 0:
            raising[index - 1, index] = math.sqrt(
                spin * (spin + 1.0)
                - magnetic_value * (magnetic_value + 1.0)
            )
        if index < local_dimension - 1:
            lowering[index + 1, index] = math.sqrt(
                spin * (spin + 1.0)
                - magnetic_value * (magnetic_value - 1.0)
            )
    return {
        "Sx": 0.5 * (raising + lowering),
        "Sy": -0.5j * (raising - lowering),
        "Sz": np.diag(magnetic_values).astype(complex),
    }


def _finite_cluster_ed(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "finite_cluster_ed",
            "blocker": "model simplification did not complete",
        }
    normalized = product_result.get("normalized_model", {})
    lattice = normalized.get("lattice", {})
    lattice_structure = normalized.get("lattice_structure", {})
    local_hilbert = normalized.get("local_hilbert", {})
    basis_registry = local_hilbert.get("basis_registry", {})
    site_records = local_hilbert.get("sites", [])
    try:
        dimensions = {
            int(basis_registry[site["basis_ref"]]["dimension"])
            for site in site_records
        }
    except (KeyError, TypeError, ValueError):
        dimensions = set()
    if len(dimensions) != 1:
        return {
            "status": "unsupported",
            "task": "finite_cluster_ed",
            "blocker": "finite-cluster ED requires one uniform local dimension",
        }
    local_dimension = dimensions.pop()
    if local_dimension < 2:
        return {
            "status": "unsupported",
            "task": "finite_cluster_ed",
            "blocker": "finite-cluster ED requires a nontrivial local space",
        }

    try:
        lattice_dimension = int(lattice.get("dimension", 0))
    except (TypeError, ValueError):
        lattice_dimension = -1
    supercell_value = request.get("supercell")
    if (
        lattice_dimension not in {0, 1, 2, 3}
        or not isinstance(supercell_value, (tuple, list))
        or len(supercell_value) != lattice_dimension
        or any(
            isinstance(length, bool)
            or not isinstance(length, int)
            or length <= 0
            for length in supercell_value
        )
    ):
        return {
            "status": "invalid_request",
            "task": "finite_cluster_ed",
            "blocker": "supercell must contain one positive integer per periodic dimension",
        }
    shape = tuple(int(length) for length in supercell_value)
    cells = (
        list(product(*(range(length) for length in shape)))
        if shape
        else [()]
    )
    basis_sites = lattice_structure.get("basis_sites", [])
    basis_count = len(basis_sites)
    if basis_count == 0:
        return {
            "status": "invalid_model",
            "task": "finite_cluster_ed",
            "blocker": "finite-cluster ED requires lattice basis sites",
        }
    site_count = len(cells) * basis_count
    matrix_dimension = local_dimension**site_count
    if matrix_dimension > 4096:
        return {
            "status": "unsupported",
            "task": "finite_cluster_ed",
            "blocker": "finite-cluster Hilbert dimension exceeds 4096",
        }
    site_index = {
        (cell, basis): cell_index * basis_count + basis
        for cell_index, cell in enumerate(cells)
        for basis in range(basis_count)
    }

    orbit_by_ref = {
        orbit.get("orbit_ref"): orbit
        for orbit in lattice_structure.get("bond_orbits", [])
        if isinstance(orbit, Mapping) and orbit.get("orbit_ref")
    }

    def orbit_edges(orbit):
        built = []
        for cell in cells:
            for member in orbit.get("members", []):
                source = int(member["source"])
                target = int(member["target"])
                translation = member["translation"]
                target_cell = tuple(
                    (cell[axis] + int(translation[axis])) % shape[axis]
                    for axis in range(lattice_dimension)
                )
                built.append(
                    (
                        site_index[(cell, source)],
                        site_index[(target_cell, target)],
                    )
                )
        return built

    term_orbit_map = request.get("term_orbit_map")
    edges_by_term_kind = {}
    try:
        if isinstance(term_orbit_map, Mapping) and term_orbit_map:
            for term_kind, orbit_ref in term_orbit_map.items():
                if (
                    not isinstance(term_kind, str)
                    or not term_kind
                    or orbit_ref not in orbit_by_ref
                ):
                    raise ValueError("invalid term-to-orbit mapping")
                edges_by_term_kind[term_kind] = orbit_edges(
                    orbit_by_ref[orbit_ref]
                )
        else:
            orbit_ref = request.get("bond_orbit_ref")
            if orbit_ref not in orbit_by_ref:
                raise ValueError("missing selected bond orbit")
            edges_by_term_kind[None] = orbit_edges(orbit_by_ref[orbit_ref])
    except (IndexError, KeyError, TypeError, ValueError):
        return {
            "status": "invalid_request",
            "task": "finite_cluster_ed",
            "blocker": "finite-cluster ED has an invalid term-to-orbit selection",
        }
    if any(not edges for edges in edges_by_term_kind.values()):
        return {
            "status": "invalid_model",
            "task": "finite_cluster_ed",
            "blocker": "a selected bond orbit contains no bonds",
        }

    canonical = product_result.get("canonical_model", {})
    if any(
        canonical.get(kind, [])
        for kind in ("one_body", "three_body", "four_body", "higher_body")
    ):
        return {
            "status": "unsupported",
            "task": "finite_cluster_ed",
            "blocker": "current finite-cluster ED supports two-body terms only",
        }
    parsed_terms = []
    for term in canonical.get("two_body", []):
        factors = []
        for token in str(term.get("canonical_label", "")).split():
            match = re.fullmatch(r"(?P<operator>S[xyz])@(?P<site>[01])", token)
            if match is None:
                return {
                    "status": "unsupported",
                    "task": "finite_cluster_ed",
                    "blocker": "finite-cluster ED supports Cartesian two-spin terms",
                }
            factors.append(
                (match.group("operator"), int(match.group("site")))
            )
        try:
            coefficient = complex(term.get("coefficient"))
        except (TypeError, ValueError):
            coefficient = complex(math.nan, math.nan)
        if (
            len(factors) != 2
            or not math.isfinite(coefficient.real)
            or not math.isfinite(coefficient.imag)
        ):
            return {
                "status": "invalid_model",
                "task": "finite_cluster_ed",
                "blocker": "finite-cluster terms must have finite coefficients",
            }
        term_kind = term.get("block_kind")
        if term_orbit_map:
            if term_kind not in edges_by_term_kind:
                return {
                    "status": "invalid_model",
                    "task": "finite_cluster_ed",
                    "blocker": "canonical term has no selected bond orbit",
                }
        else:
            term_kind = None
        parsed_terms.append((coefficient, factors, term_kind))
    if not parsed_terms:
        return {
            "status": "invalid_model",
            "task": "finite_cluster_ed",
            "blocker": "finite-cluster ED found no two-body terms",
        }

    spin_operators = _spin_matrices(local_dimension)
    identity = np.eye(local_dimension, dtype=complex)
    hamiltonian = np.zeros(
        (matrix_dimension, matrix_dimension), dtype=complex
    )
    for coefficient, factors, term_kind in parsed_terms:
        for left, right in edges_by_term_kind[term_kind]:
            local_operators = [identity for _ in range(site_count)]
            for operator_name, template_site in factors:
                actual_site = left if template_site == 0 else right
                local_operators[actual_site] = (
                    local_operators[actual_site]
                    @ spin_operators[operator_name]
                )
            embedded = np.asarray([[1.0 + 0.0j]])
            for local_operator in local_operators:
                embedded = np.kron(embedded, local_operator)
            hamiltonian += coefficient * embedded
    if not np.allclose(
        hamiltonian, hamiltonian.conj().T, atol=1.0e-10, rtol=0.0
    ):
        return {
            "status": "invalid_model",
            "task": "finite_cluster_ed",
            "blocker": "assembled finite-cluster Hamiltonian is not Hermitian",
        }
    eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
    eigenvalues = eigenvalues.real
    ground_energy = float(eigenvalues[0])
    ground_degeneracy = int(
        np.count_nonzero(
            np.isclose(eigenvalues, ground_energy, atol=1.0e-9, rtol=0.0)
        )
    )
    excited = eigenvalues[ground_degeneracy:]
    spectral_gap = (
        float(excited[0] - ground_energy) if len(excited) else 0.0
    )
    observable = request.get("observable", "spectrum")
    ground_space_total_spin_squared = None
    commutator_norms = None
    if observable == "all_operator_products_commute":
        operator_products = request.get("commuting_operator_products")
        if not isinstance(operator_products, (tuple, list)) or not operator_products:
            return {
                "status": "invalid_request",
                "task": "finite_cluster_ed",
                "blocker": "commuting-operator analysis requires operator products",
            }
        commutator_norms = []
        for specification in operator_products:
            if not isinstance(specification, Mapping):
                return {
                    "status": "invalid_request",
                    "task": "finite_cluster_ed",
                    "blocker": "operator-product specifications must be mappings",
                }
            operator_name = specification.get("operator")
            sites = specification.get("sites")
            if (
                operator_name not in spin_operators
                or not isinstance(sites, (tuple, list))
                or not sites
                or any(
                    isinstance(site, bool)
                    or not isinstance(site, int)
                    or site < 0
                    or site >= site_count
                    for site in sites
                )
            ):
                return {
                    "status": "invalid_request",
                    "task": "finite_cluster_ed",
                    "blocker": "operator-product sites or operator are invalid",
                }
            local_operators = [identity for _ in range(site_count)]
            for site in sites:
                local_operators[site] = (
                    local_operators[site] @ spin_operators[operator_name]
                )
            candidate = np.asarray([[1.0 + 0.0j]])
            for local_operator in local_operators:
                candidate = np.kron(candidate, local_operator)
            commutator = hamiltonian @ candidate - candidate @ hamiltonian
            commutator_norms.append(float(np.linalg.norm(commutator)))
        value = max(commutator_norms) <= 1.0e-10
    elif observable == "zero_total_spin_ground_space":
        total_spin_squared = np.zeros_like(hamiltonian)
        for operator_name in ("Sx", "Sy", "Sz"):
            total_component = np.zeros_like(hamiltonian)
            for site in range(site_count):
                local_operators = [identity for _ in range(site_count)]
                local_operators[site] = spin_operators[operator_name]
                embedded = np.asarray([[1.0 + 0.0j]])
                for local_operator in local_operators:
                    embedded = np.kron(embedded, local_operator)
                total_component += embedded
            total_spin_squared += total_component @ total_component
        ground_basis = eigenvectors[:, :ground_degeneracy]
        projected = (
            ground_basis.conj().T @ total_spin_squared @ ground_basis
        )
        ground_space_total_spin_squared = [
            float(item)
            for item in np.linalg.eigvalsh(projected).real
        ]
        value = all(
            abs(item) <= 1.0e-9
            for item in ground_space_total_spin_squared
        )
    elif observable == "ground_state_energy":
        value = ground_energy
    elif observable == "spectral_gap":
        value = spectral_gap
    elif observable == "ground_state_degeneracy":
        value = ground_degeneracy
    elif observable == "ground_state_summary":
        value = {
            "energy_per_site": ground_energy / site_count,
            "ground_state_degeneracy": ground_degeneracy,
        }
    else:
        value = [float(item) for item in eigenvalues]
    result = {
        "status": "ok",
        "task": "finite_cluster_ed",
        "observable": observable,
        "units": request.get("units", "model_energy_units"),
        "value": value,
        "site_count": site_count,
        "bond_count": sum(
            len(edges) for edges in edges_by_term_kind.values()
        ),
        "matrix_dimension": matrix_dimension,
        "ground_state_energy": ground_energy,
        "ground_state_degeneracy": ground_degeneracy,
        "spectral_gap": spectral_gap,
        "eigenvalues": [float(item) for item in eigenvalues],
    }
    if ground_space_total_spin_squared is not None:
        result["ground_space_total_spin_squared"] = (
            ground_space_total_spin_squared
        )
    if commutator_norms is not None:
        result["commutator_norms"] = commutator_norms
        result["maximum_commutator_norm"] = max(commutator_norms)
    return result


def _ising_chain_free_fermion(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "ising_chain_free_fermion",
            "blocker": "model simplification did not complete",
        }
    normalized = product_result.get("normalized_model", {})
    lattice = normalized.get("lattice", {})
    basis_sites = normalized.get("lattice_structure", {}).get(
        "basis_sites", []
    )
    canonical = product_result.get("canonical_model", {})
    two_body = canonical.get("two_body", [])
    onsite_terms = canonical.get("onsite_terms", [])
    if (
        lattice.get("kind") != "chain"
        or lattice.get("dimension") != 1
        or len(basis_sites) != 1
        or len(two_body) != 1
        or two_body[0].get("canonical_label") != "Sz@0 Sz@1"
        or len(onsite_terms) != 1
        or onsite_terms[0].get("kind") != "linear_spin_cartesian"
    ):
        return {
            "status": "unsupported",
            "task": "ising_chain_free_fermion",
            "blocker": (
                "analysis requires a one-site transverse-field Ising chain"
            ),
        }
    try:
        exchange_coefficient = float(two_body[0]["coefficient"])
        field_vector = [
            float(value)
            for value in onsite_terms[0]["payload"]["vector"]
        ]
    except (KeyError, TypeError, ValueError):
        return {
            "status": "invalid_model",
            "task": "ising_chain_free_fermion",
            "blocker": "Ising exchange or transverse field is malformed",
        }
    if (
        len(field_vector) != 3
        or any(not math.isfinite(value) for value in field_vector)
        or not math.isfinite(exchange_coefficient)
        or abs(field_vector[1]) > 1.0e-12
        or abs(field_vector[2]) > 1.0e-12
    ):
        return {
            "status": "unsupported",
            "task": "ising_chain_free_fermion",
            "blocker": "field must be finite and purely transverse",
        }
    exchange = abs(exchange_coefficient) / 4.0
    field = abs(field_vector[0]) / 2.0
    if exchange <= 0.0:
        return {
            "status": "unsupported",
            "task": "ising_chain_free_fermion",
            "blocker": "Ising exchange magnitude must be positive",
        }
    momenta = request.get("momenta", [0.0, math.pi])
    if (
        not isinstance(momenta, (tuple, list))
        or not momenta
        or any(
            isinstance(momentum, bool)
            or not isinstance(momentum, (int, float))
            or not math.isfinite(float(momentum))
            for momentum in momenta
        )
    ):
        return {
            "status": "invalid_request",
            "task": "ising_chain_free_fermion",
            "blocker": "momenta must be a nonempty finite numeric sequence",
        }

    def dispersion(momentum, transverse_field):
        return 2.0 * math.sqrt(
            exchange * exchange
            + transverse_field * transverse_field
            - 2.0
            * exchange
            * transverse_field
            * math.cos(float(momentum))
        )

    critical_field = exchange
    samples = [
        {
            "momentum": float(momentum),
            "energy": dispersion(momentum, field),
        }
        for momentum in momenta
    ]
    observable = request.get("observable", "critical_field")
    value = (
        critical_field
        if observable == "critical_field"
        else min(sample["energy"] for sample in samples)
    )
    return {
        "status": "ok",
        "task": "ising_chain_free_fermion",
        "observable": observable,
        "units": request.get("units", "model_energy_units"),
        "value": value,
        "exchange": exchange,
        "field": field,
        "current_gap": 2.0 * abs(exchange - field),
        "critical_gap_residual": dispersion(0.0, critical_field),
        "dispersion_samples": samples,
    }


def _xx_chain_free_fermion(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "xx_chain_free_fermion",
            "blocker": "model simplification did not complete",
        }
    normalized = product_result.get("normalized_model", {})
    canonical = product_result.get("canonical_model", {})
    lattice = normalized.get("lattice", {})
    coefficients = {
        term.get("canonical_label"): term.get("coefficient")
        for term in canonical.get("two_body", [])
    }
    try:
        exchange_x = float(coefficients["Sx@0 Sx@1"])
        exchange_y = float(coefficients["Sy@0 Sy@1"])
    except (KeyError, TypeError, ValueError):
        return {
            "status": "unsupported",
            "task": "xx_chain_free_fermion",
            "blocker": "analysis requires finite SxSx and SySy chain couplings",
        }
    if (
        lattice.get("kind") != "chain"
        or lattice.get("dimension") != 1
        or len(coefficients) != 2
        or canonical.get("onsite_terms", [])
        or not math.isfinite(exchange_x)
        or not math.isfinite(exchange_y)
        or abs(exchange_x - exchange_y) > 1.0e-12
    ):
        return {
            "status": "unsupported",
            "task": "xx_chain_free_fermion",
            "blocker": "analysis currently requires an isotropic zero-field XX chain",
        }
    grid_sizes = request.get("grid_sizes")
    if (
        not isinstance(grid_sizes, (tuple, list))
        or len(grid_sizes) < 2
        or any(
            isinstance(size, bool)
            or not isinstance(size, int)
            or size < 16
            or size > 1_000_000
            for size in grid_sizes
        )
        or any(
            right <= left
            for left, right in zip(grid_sizes, grid_sizes[1:])
        )
    ):
        return {
            "status": "invalid_request",
            "task": "xx_chain_free_fermion",
            "blocker": "grid_sizes must contain at least two increasing sizes",
        }
    exchange = 0.5 * (exchange_x + exchange_y)
    estimates = []
    for size in grid_sizes:
        step = 2.0 * math.pi / size
        occupied_sum = math.fsum(
            min(
                0.0,
                exchange * math.cos(-math.pi + (index + 0.5) * step),
            )
            for index in range(size)
        )
        estimates.append(
            {
                "grid_size": size,
                "energy_per_site": occupied_sum / size,
            }
        )
    refinement_difference = abs(
        estimates[-1]["energy_per_site"]
        - estimates[-2]["energy_per_site"]
    )
    return {
        "status": "ok",
        "task": "xx_chain_free_fermion",
        "observable": request.get(
            "observable", "ground_state_energy_per_site"
        ),
        "units": request.get("units", "model_energy_units"),
        "value": estimates[-1]["energy_per_site"],
        "exchange": exchange,
        "grid_estimates": estimates,
        "refinement_difference": refinement_difference,
    }


def _xy_chain_free_fermion_boundaries(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "xy_chain_free_fermion_boundaries",
            "blocker": "model simplification did not complete",
        }
    canonical = product_result.get("canonical_model", {})
    lattice = product_result.get("normalized_model", {}).get("lattice", {})
    coefficients = {
        term.get("canonical_label"): term.get("coefficient")
        for term in canonical.get("two_body", [])
    }
    try:
        exchange_x = float(coefficients["Sx@0 Sx@1"])
        exchange_y = float(coefficients["Sy@0 Sy@1"])
    except (KeyError, TypeError, ValueError):
        exchange_x = math.nan
        exchange_y = math.nan
    if (
        lattice.get("kind") != "chain"
        or lattice.get("dimension") != 1
        or len(coefficients) != 2
        or not math.isfinite(exchange_x)
        or not math.isfinite(exchange_y)
        or exchange_x == 0.0
        or exchange_y == 0.0
        or exchange_x * exchange_y <= 0.0
    ):
        return {
            "status": "unsupported",
            "task": "xy_chain_free_fermion_boundaries",
            "blocker": "analysis requires a finite same-sign anisotropic XY chain",
        }
    magnitude_x = abs(exchange_x)
    magnitude_y = abs(exchange_y)
    exchange = 0.5 * (magnitude_x + magnitude_y)
    input_anisotropy = (magnitude_x - magnitude_y) / (
        magnitude_x + magnitude_y
    )
    value = {
        "ising_critical_field": exchange,
        "anisotropy_transition_gamma": 0.0,
    }
    return {
        "status": "ok",
        "task": "xy_chain_free_fermion_boundaries",
        "observable": request.get("observable", "critical_boundaries"),
        "units": request.get("units", "model_parameter_units"),
        "value": value,
        "exchange": exchange,
        "input_anisotropy": input_anisotropy,
        **value,
    }


def _xxx_chain_bethe_integral(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "xxx_chain_bethe_integral",
            "blocker": "model simplification did not complete",
        }
    canonical = product_result.get("canonical_model", {})
    lattice = product_result.get("normalized_model", {}).get("lattice", {})
    coefficients = {
        term.get("canonical_label"): term.get("coefficient")
        for term in canonical.get("two_body", [])
    }
    try:
        exchanges = [
            float(coefficients[f"S{axis}@0 S{axis}@1"])
            for axis in ("x", "y", "z")
        ]
        cutoff = float(request.get("integration_cutoff", 40.0))
    except (KeyError, TypeError, ValueError):
        exchanges = [math.nan]
        cutoff = math.nan
    orders = request.get("quadrature_orders", [64, 128])
    if (
        lattice.get("kind") != "chain"
        or lattice.get("dimension") != 1
        or len(coefficients) != 3
        or any(not math.isfinite(value) for value in exchanges)
        or min(exchanges) <= 0.0
        or max(exchanges) - min(exchanges) > 1.0e-12
        or canonical.get("onsite_terms", [])
        or not math.isfinite(cutoff)
        or cutoff <= 0.0
        or not isinstance(orders, (tuple, list))
        or len(orders) < 2
        or any(
            isinstance(order, bool)
            or not isinstance(order, int)
            or order < 8
            or order > 4096
            for order in orders
        )
        or any(right <= left for left, right in zip(orders, orders[1:]))
    ):
        return {
            "status": "unsupported",
            "task": "xxx_chain_bethe_integral",
            "blocker": "analysis requires a positive isotropic zero-field spin-half chain",
        }
    exchange = math.fsum(exchanges) / 3.0
    estimates = []
    for order in orders:
        nodes, weights = np.polynomial.legendre.leggauss(order)
        points = 0.5 * cutoff * (nodes + 1.0)
        integral = 0.5 * cutoff * float(
            np.dot(weights, 1.0 / (np.exp(points) + 1.0))
        )
        estimates.append(
            {
                "quadrature_order": order,
                "energy_per_site": exchange * (0.25 - integral),
            }
        )
    value = estimates[-1]["energy_per_site"]
    refinement_difference = abs(
        value - estimates[-2]["energy_per_site"]
    )
    return {
        "status": "ok",
        "task": "xxx_chain_bethe_integral",
        "observable": request.get(
            "observable", "ground_state_energy_per_site"
        ),
        "units": request.get("units", "J"),
        "value": value,
        "exchange": exchange,
        "quadrature_estimates": estimates,
        "refinement_difference": refinement_difference,
        "integration_cutoff": cutoff,
    }


def _fourier_exchange_spectrum(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "fourier_exchange_spectrum",
            "blocker": "model simplification did not complete",
        }
    solver_model = product_result.get("solver_model")
    if isinstance(solver_model, Mapping) and solver_model.get("schema_version") == "canonical-hamiltonian/v1":
        return _canonical_tensor_fourier_exchange_spectrum(product_result, request)

    normalized = product_result.get("normalized_model", {})
    lattice = normalized.get("lattice", {})
    structure = normalized.get("lattice_structure", {})
    canonical = product_result.get("canonical_model", {})
    try:
        dimension = int(lattice.get("dimension"))
    except (TypeError, ValueError):
        dimension = 0
    basis_count = len(structure.get("basis_sites", []))
    term_orbit_map = request.get("term_orbit_map")
    momenta = request.get("reduced_momenta")
    if (
        dimension not in {1, 2, 3}
        or basis_count < 1
        or not isinstance(term_orbit_map, Mapping)
        or not term_orbit_map
        or not isinstance(momenta, (tuple, list))
        or not momenta
    ):
        return {
            "status": "invalid_request",
            "task": "fourier_exchange_spectrum",
            "blocker": "analysis requires a periodic lattice, orbit map, and momenta",
        }
    orbit_by_ref = {
        orbit.get("orbit_ref"): orbit
        for orbit in structure.get("bond_orbits", [])
        if isinstance(orbit, Mapping)
    }
    terms_by_block = {}
    for term in canonical.get("two_body", []):
        terms_by_block.setdefault(
            term.get("block_kind") or "default", []
        ).append(term)
    couplings = {}
    for block_kind, orbit_ref in term_orbit_map.items():
        terms = terms_by_block.get(block_kind, [])
        labels = {term.get("canonical_label") for term in terms}
        try:
            values = [float(term.get("coefficient")) for term in terms]
        except (TypeError, ValueError):
            values = [math.nan]
        if (
            labels != {
                "Sx@0 Sx@1",
                "Sy@0 Sy@1",
                "Sz@0 Sz@1",
            }
            or len(values) != 3
            or any(not math.isfinite(value) for value in values)
            or max(values) - min(values) > 1.0e-12
            or orbit_ref not in orbit_by_ref
        ):
            return {
                "status": "unsupported",
                "task": "fourier_exchange_spectrum",
                "blocker": "each mapped orbit requires one isotropic Heisenberg block",
            }
        couplings[block_kind] = math.fsum(values) / 3.0
    spectra = []
    flat_projectors = []
    flat_band_count = request.get("flat_band_count")
    fourier_model = {
        "lattice": {"sublattices": basis_count},
        "bonds": [
            {
                "source": int(member["source"]),
                "target": int(member["target"]),
                "vector": list(member["translation"]),
                "matrix": (float(couplings[block_kind]) * np.eye(3)).tolist(),
            }
            for block_kind, orbit_ref in term_orbit_map.items()
            for member in orbit_by_ref[orbit_ref].get("members", [])
        ],
    }
    scalar_indices = [3 * site for site in range(basis_count)]
    for momentum_value in momenta:
        if (
            not isinstance(momentum_value, (tuple, list))
            or len(momentum_value) != dimension
        ):
            return {
                "status": "invalid_request",
                "task": "fourier_exchange_spectrum",
                "blocker": "each reduced momentum must match lattice dimension",
            }
        try:
            momentum = tuple(float(value) for value in momentum_value)
        except (TypeError, ValueError):
            momentum = (math.nan,)
        if any(not math.isfinite(value) for value in momentum):
            return {
                "status": "invalid_request",
                "task": "fourier_exchange_spectrum",
                "blocker": "momenta must be finite",
            }
        try:
            tensor_matrix = fourier_exchange_matrix(fourier_model, momentum)
        except (IndexError, KeyError, TypeError, ValueError):
            return {
                "status": "invalid_model",
                "task": "fourier_exchange_spectrum",
                "blocker": "bond-orbit member is malformed",
            }
        matrix = tensor_matrix[np.ix_(scalar_indices, scalar_indices)]
        eigenvalues, eigenvectors = np.linalg.eigh(matrix)
        eigenvalues = eigenvalues.real
        spectra.append(
            {
                "reduced_momentum": list(momentum),
                "eigenvalues": [float(value) for value in eigenvalues],
            }
        )
        if (
            isinstance(flat_band_count, int)
            and not isinstance(flat_band_count, bool)
            and 0 < flat_band_count < basis_count
        ):
            selected = eigenvectors[:, :flat_band_count]
            flat_projectors.append(selected @ selected.conj().T)
    observable = request.get("observable", "exchange_eigenvalues")
    value = [item["eigenvalues"] for item in spectra]
    diagnostics = {}
    if observable == "flat_band_constraint_summary":
        if len(flat_projectors) < 2:
            return {
                "status": "invalid_request",
                "task": "fourier_exchange_spectrum",
                "blocker": "flat-band diagnostics require a valid count and two momenta",
            }
        selected_energies = [
            eigenvalue
            for item in spectra
            for eigenvalue in item["eigenvalues"][:flat_band_count]
        ]
        flat_band_width = max(selected_energies) - min(selected_energies)
        directional_difference = float(
            np.linalg.norm(flat_projectors[0] - flat_projectors[1])
        )
        value = {
            "zero_total_spin_per_tetrahedron": flat_band_width <= 1.0e-10,
            "pinch_points": directional_difference > 1.0e-3,
        }
        diagnostics = {
            "flat_band_width": flat_band_width,
            "directional_projector_difference": directional_difference,
        }
    return {
        "status": "ok",
        "task": "fourier_exchange_spectrum",
        "observable": observable,
        "units": request.get("units", "model_energy_units"),
        "value": value,
        "spectra": spectra,
        "minimum_eigenvalue": min(
            item["eigenvalues"][0] for item in spectra
        ),
        "matrix_size": 3 * basis_count,
        "backend": {
            "module": "classical.lt_fourier_exchange",
            "function": "classical.lt_fourier_exchange.fourier_exchange_matrix",
        },
        **diagnostics,
    }


def _complex_payload(value, *, tolerance=1.0e-14):
    array = np.asarray(value, dtype=complex)

    def encode(child):
        if isinstance(child, list):
            return [encode(entry) for entry in child]
        scalar = complex(child)
        real = 0.0 if abs(scalar.real) <= tolerance else float(scalar.real)
        imag = 0.0 if abs(scalar.imag) <= tolerance else float(scalar.imag)
        return real if imag == 0.0 else {"real": real, "imag": imag}

    return encode(array.tolist())


def _canonical_tensor_fourier_exchange_spectrum(product_result, request):
    model = product_result["solver_model"]
    require_current_symmetry_stamp(model, product_result.get("symmetry_validation_stamp"))
    basis_count = len((model.get("lattice_structure") or {}).get("basis_sites") or [])
    momenta = request.get("reduced_momenta")
    if basis_count < 1 or not isinstance(momenta, (list, tuple)) or not momenta:
        return {
            "status": "invalid_request",
            "task": "fourier_exchange_spectrum",
            "blocker": "analysis requires basis sites and reduced momenta",
        }
    bonds = []
    unsupported = []
    for term in list(model.get("terms") or []):
        if int(term.get("arity", 0)) != 2 or term.get("operator_family") not in {
            "bilinear_exchange_tensor",
            "bilinear_exchange_matrix",
        }:
            unsupported.append(str(term.get("term_ref") or ""))
            continue
        cluster = list(term.get("cluster") or [])
        if len(cluster) != 2:
            unsupported.append(str(term.get("term_ref") or ""))
            continue
        bonds.append(
            {
                "source": int(cluster[0]["site"]),
                "target": int(cluster[1]["site"]),
                "vector": [
                    int(cluster[1]["translation"][axis]) - int(cluster[0]["translation"][axis])
                    for axis in range(3)
                ],
                "matrix": term.get("coefficient"),
            }
        )
    if unsupported:
        return {
            "status": "unsupported",
            "task": "fourier_exchange_spectrum",
            "blocker": "solver-capability-mismatch",
            "unsupported_term_refs": unsupported,
        }
    if not bonds:
        return {
            "status": "invalid_model",
            "task": "fourier_exchange_spectrum",
            "blocker": "no bilinear exchange terms",
        }
    fourier_model = {"lattice": {"sublattices": basis_count}, "bonds": bonds}
    spectra = []
    for q_value in momenta:
        if not isinstance(q_value, (list, tuple)) or not 1 <= len(q_value) <= 3:
            return {
                "status": "invalid_request",
                "task": "fourier_exchange_spectrum",
                "blocker": "each reduced momentum must have one to three components",
            }
        q = [float(value) for value in q_value]
        if any(not math.isfinite(value) for value in q):
            return {
                "status": "invalid_request",
                "task": "fourier_exchange_spectrum",
                "blocker": "momenta must be finite",
            }
        matrix = fourier_exchange_matrix(fourier_model, q)
        eigenvalues, eigenvectors = np.linalg.eigh(matrix)
        projectors = [
            eigenvectors[:, band : band + 1] @ eigenvectors[:, band : band + 1].conjugate().T
            for band in range(eigenvectors.shape[1])
        ]
        spectra.append(
            {
                "reduced_momentum": q,
                "eigenvalues": [float(value) for value in eigenvalues.real],
                "eigenvectors": _complex_payload(eigenvectors),
                "eigenprojectors": [_complex_payload(projector) for projector in projectors],
            }
        )
    return {
        "status": "ok",
        "task": "fourier_exchange_spectrum",
        "observable": request.get("observable", "exchange_eigenvalues"),
        "units": request.get("units", "model_energy_units"),
        "value": [record["eigenvalues"] for record in spectra],
        "spectra": spectra,
        "minimum_eigenvalue": min(record["eigenvalues"][0] for record in spectra),
        "matrix_size": 3 * basis_count,
        "solver_model_hash": product_result["symmetry_validation_stamp"]["hamiltonian_hash"],
        "backend": {
            "module": "classical.lt_fourier_exchange",
            "function": "classical.lt_fourier_exchange.fourier_exchange_matrix",
        },
    }


def _bravais_fourier_competing_order_boundary(product_result, request):
    normalized = (
        product_result.get("normalized_model", {})
        if isinstance(product_result, Mapping)
        else {}
    )
    structure = normalized.get("lattice_structure", {})
    momenta = request.get("competing_momenta")
    reference_block = request.get("reference_block")
    varied_block = request.get("varied_block")
    term_orbit_map = request.get("term_orbit_map")
    if (
        len(structure.get("basis_sites", [])) != 1
        or not isinstance(momenta, (tuple, list))
        or len(momenta) != 2
        or not isinstance(reference_block, str)
        or not isinstance(varied_block, str)
        or reference_block == varied_block
        or not isinstance(term_orbit_map, Mapping)
        or set(term_orbit_map) != {reference_block, varied_block}
    ):
        return {
            "status": "invalid_request",
            "task": "bravais_fourier_competing_order_boundary",
            "blocker": "analysis requires one Bravais site, two blocks, and two momenta",
        }

    canonical = product_result.get("canonical_model", {})

    def unit_block_product(selected_block):
        terms = []
        for term in canonical.get("two_body", []):
            copied = dict(term)
            copied["coefficient"] = (
                1.0 if term.get("block_kind") == selected_block else 0.0
            )
            terms.append(copied)
        return {
            **dict(product_result),
            "canonical_model": {**dict(canonical), "two_body": terms},
        }

    fourier_request = {
        "term_orbit_map": dict(term_orbit_map),
        "reduced_momenta": list(momenta),
    }
    reference = _fourier_exchange_spectrum(
        unit_block_product(reference_block), fourier_request
    )
    varied = _fourier_exchange_spectrum(
        unit_block_product(varied_block), fourier_request
    )
    if reference.get("status") != "ok" or varied.get("status") != "ok":
        return {
            "status": "unsupported",
            "task": "bravais_fourier_competing_order_boundary",
            "blocker": "Fourier decomposition of competing interactions failed",
        }
    reference_delta = (
        reference["spectra"][0]["eigenvalues"][0]
        - reference["spectra"][1]["eigenvalues"][0]
    )
    varied_delta = (
        varied["spectra"][0]["eigenvalues"][0]
        - varied["spectra"][1]["eigenvalues"][0]
    )
    if abs(varied_delta) <= 1.0e-14:
        return {
            "status": "unsupported",
            "task": "bravais_fourier_competing_order_boundary",
            "blocker": "competing momenta do not separate the varied orbit",
        }
    ratio = -reference_delta / varied_delta
    residual = abs(reference_delta + ratio * varied_delta)
    return {
        "status": "ok",
        "task": "bravais_fourier_competing_order_boundary",
        "observable": request.get("observable", "critical_ratio"),
        "units": request.get("units", f"{varied_block}/{reference_block}"),
        "value": ratio,
        "reference_energy_difference": reference_delta,
        "varied_energy_difference": varied_delta,
        "energy_crossing_residual": residual,
        "competing_momenta": [list(momentum) for momentum in momenta],
    }


def _fourier_curvature_instability_boundary(product_result, request):
    normalized = (
        product_result.get("normalized_model", {})
        if isinstance(product_result, Mapping)
        else {}
    )
    lattice = normalized.get("lattice", {})
    try:
        dimension = int(lattice.get("dimension"))
        center = tuple(float(value) for value in request.get("central_momentum"))
        displacement = tuple(
            float(value) for value in request.get("momentum_displacement")
        )
        lower, upper = (
            float(value) for value in request.get("ratio_bracket")
        )
        tolerance = float(request.get("absolute_tolerance", 1.0e-10))
    except (TypeError, ValueError):
        dimension = 0
        center = ()
        displacement = ()
        lower = upper = tolerance = math.nan
    reference_block = request.get("reference_block")
    varied_block = request.get("varied_block")
    term_orbit_map = request.get("term_orbit_map")
    displacement_norm_squared = math.fsum(
        value * value for value in displacement
    )
    if (
        dimension not in {1, 2, 3}
        or len(center) != dimension
        or len(displacement) != dimension
        or not all(math.isfinite(value) for value in center + displacement)
        or displacement_norm_squared <= 0.0
        or not math.isfinite(lower)
        or not math.isfinite(upper)
        or lower >= upper
        or not math.isfinite(tolerance)
        or tolerance <= 0.0
        or not isinstance(reference_block, str)
        or not isinstance(varied_block, str)
        or reference_block == varied_block
        or not isinstance(term_orbit_map, Mapping)
        or set(term_orbit_map) != {reference_block, varied_block}
    ):
        return {
            "status": "invalid_request",
            "task": "fourier_curvature_instability_boundary",
            "blocker": "invalid Fourier-curvature boundary request",
        }
    canonical = product_result.get("canonical_model", {})
    plus = [center[index] + displacement[index] for index in range(dimension)]
    minus = [center[index] - displacement[index] for index in range(dimension)]

    def curvature(ratio):
        terms = []
        for term in canonical.get("two_body", []):
            copied = dict(term)
            block_kind = term.get("block_kind")
            if block_kind == reference_block:
                copied["coefficient"] = 1.0
            elif block_kind == varied_block:
                copied["coefficient"] = ratio
            terms.append(copied)
        modified = {
            **dict(product_result),
            "canonical_model": {**dict(canonical), "two_body": terms},
        }
        spectrum = _fourier_exchange_spectrum(
            modified,
            {
                "term_orbit_map": dict(term_orbit_map),
                "reduced_momenta": [list(center), plus, minus],
            },
        )
        if spectrum.get("status") != "ok":
            raise ValueError("Fourier spectrum construction failed")
        energies = [
            item["eigenvalues"][0] for item in spectrum["spectra"]
        ]
        return (energies[1] + energies[2] - 2.0 * energies[0]) / (
            displacement_norm_squared
        )

    try:
        lower_value = curvature(lower)
        upper_value = curvature(upper)
    except ValueError as exc:
        return {
            "status": "unsupported",
            "task": "fourier_curvature_instability_boundary",
            "blocker": str(exc),
        }
    if lower_value * upper_value > 0.0:
        return {
            "status": "not_bracketed",
            "task": "fourier_curvature_instability_boundary",
            "blocker": "curvature has the same sign at both ratio endpoints",
        }
    ratio = 0.5 * (lower + upper)
    residual = abs(curvature(ratio))
    for _iteration in range(96):
        ratio = 0.5 * (lower + upper)
        value = curvature(ratio)
        residual = abs(value)
        if upper - lower <= tolerance:
            break
        if lower_value * value <= 0.0:
            upper = ratio
            upper_value = value
        else:
            lower = ratio
            lower_value = value
    return {
        "status": "ok",
        "task": "fourier_curvature_instability_boundary",
        "observable": request.get("observable", "critical_ratio"),
        "units": request.get("units", f"{varied_block}/{reference_block}"),
        "value": ratio,
        "curvature_residual": residual,
        "ratio_bracket_width": upper - lower,
        "central_momentum": list(center),
        "momentum_displacement": list(displacement),
    }


def _kitaev_majorana_field_gap(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "kitaev_majorana_field_gap",
            "blocker": "model simplification did not complete",
        }
    canonical = product_result.get("canonical_model", {})
    lattice = product_result.get("normalized_model", {}).get("lattice", {})
    couplings = {}
    for term in canonical.get("two_body", []):
        block_kind = term.get("block_kind")
        for axis in ("x", "y", "z"):
            if (
                block_kind == f"{axis}_bond"
                and term.get("canonical_label") == f"S{axis}@0 S{axis}@1"
            ):
                try:
                    couplings[axis] = float(term.get("coefficient"))
                except (TypeError, ValueError):
                    couplings[axis] = math.nan
    onsite_terms = canonical.get("onsite_terms", [])
    vector = (
        onsite_terms[0].get("payload", {}).get("vector")
        if len(onsite_terms) == 1
        else None
    )
    try:
        fields = tuple(-float(value) for value in vector)
    except (TypeError, ValueError):
        fields = (math.nan,)
    if (
        lattice.get("kind") != "honeycomb"
        or lattice.get("dimension") != 2
        or set(couplings) != {"x", "y", "z"}
        or any(not math.isfinite(value) or value <= 0.0 for value in couplings.values())
        or len(fields) != 3
        or any(not math.isfinite(value) or value == 0.0 for value in fields)
    ):
        return {
            "status": "unsupported",
            "task": "kitaev_majorana_field_gap",
            "blocker": "analysis requires positive x/y/z Kitaev bonds and a finite three-axis field",
        }
    exchange = math.fsum(couplings.values()) / 3.0
    if (
        max(couplings.values()) - min(couplings.values()) > 1.0e-12
        or max(abs(value) for value in fields) > 0.25 * exchange
    ):
        return {
            "status": "unsupported",
            "task": "kitaev_majorana_field_gap",
            "blocker": "current Majorana mass formula requires isotropic weak-field couplings",
        }
    phase = 2.0 * math.pi / 3.0
    dirac_hopping = (
        couplings["z"]
        + couplings["x"] * complex(math.cos(phase), math.sin(phase))
        + couplings["y"] * complex(math.cos(-phase), math.sin(-phase))
    )
    dirac_residual = abs(dirac_hopping)
    mass = 6.0 * math.sqrt(3.0) * math.prod(fields) / (exchange**2)
    gap = 2.0 * abs(mass)
    mass_sign = 1 if mass > 0.0 else -1
    value = gap > 0.0 and dirac_residual <= 1.0e-12
    return {
        "status": "ok",
        "task": "kitaev_majorana_field_gap",
        "observable": request.get(
            "observable", "field_opens_non_abelian_gap"
        ),
        "units": request.get("units", "dimensionless"),
        "value": value,
        "exchange": exchange,
        "field_components": list(fields),
        "majorana_mass": mass,
        "majorana_gap": gap,
        "mass_sign": mass_sign,
        "dirac_residual": dirac_residual,
    }


def _pauli_stabilizer_rank(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "pauli_stabilizer_rank",
            "blocker": "model simplification did not complete",
        }
    qubit_count = request.get("qubit_count")
    if (
        isinstance(qubit_count, bool)
        or not isinstance(qubit_count, int)
        or not 1 <= qubit_count <= 256
    ):
        return {
            "status": "invalid_request",
            "task": "pauli_stabilizer_rank",
            "blocker": "qubit_count must be an integer from 1 through 256",
        }
    canonical = product_result.get("canonical_model", {})
    terms = []
    for body_kind in (
        "one_body", "two_body", "three_body", "four_body", "higher_body"
    ):
        terms.extend(canonical.get(body_kind, []))
    rows = []
    for term in terms:
        try:
            coefficient = complex(term.get("coefficient"))
        except (TypeError, ValueError):
            coefficient = complex(math.nan, math.nan)
        tokens = str(term.get("canonical_label", "")).split()
        parsed = [re.fullmatch(r"S(?P<axis>[xz])@(?P<site>\d+)", token) for token in tokens]
        if (
            not tokens
            or any(match is None for match in parsed)
            or not math.isfinite(coefficient.real)
            or not math.isfinite(coefficient.imag)
            or abs(coefficient) <= 1.0e-14
        ):
            return {
                "status": "unsupported",
                "task": "pauli_stabilizer_rank",
                "blocker": "stabilizers must be nonzero products of only Pauli X or Z",
            }
        axes = {match.group("axis") for match in parsed}
        sites = [int(match.group("site")) for match in parsed]
        if (
            len(axes) != 1
            or len(set(sites)) != len(sites)
            or any(site >= qubit_count for site in sites)
        ):
            return {
                "status": "unsupported",
                "task": "pauli_stabilizer_rank",
                "blocker": "each CSS stabilizer must use one axis and valid distinct qubits",
            }
        row = 0
        offset = 0 if next(iter(axes)) == "x" else qubit_count
        for site in sites:
            row ^= 1 << (offset + site)
        rows.append(row)
    if not rows:
        return {
            "status": "unsupported",
            "task": "pauli_stabilizer_rank",
            "blocker": "no stabilizer generators were found",
        }

    commutators = []
    mask = (1 << qubit_count) - 1
    for left_index, left in enumerate(rows):
        left_x, left_z = left & mask, left >> qubit_count
        for right in rows[left_index + 1 :]:
            right_x, right_z = right & mask, right >> qubit_count
            commutators.append(
                (
                    bin(left_x & right_z).count("1")
                    + bin(left_z & right_x).count("1")
                )
                % 2
            )
    maximum_commutator = max(commutators, default=0)
    if maximum_commutator:
        return {
            "status": "invalid_model",
            "task": "pauli_stabilizer_rank",
            "blocker": "stabilizer generators do not commute",
        }
    reduced = list(rows)
    rank = 0
    for column in range(2 * qubit_count):
        pivot = next(
            (index for index in range(rank, len(reduced)) if reduced[index] & (1 << column)),
            None,
        )
        if pivot is None:
            continue
        reduced[rank], reduced[pivot] = reduced[pivot], reduced[rank]
        for row_index in range(len(reduced)):
            if row_index != rank and reduced[row_index] & (1 << column):
                reduced[row_index] ^= reduced[rank]
        rank += 1
        if rank == len(reduced):
            break
    if rank > qubit_count:
        return {
            "status": "invalid_model",
            "task": "pauli_stabilizer_rank",
            "blocker": "commuting stabilizer rank exceeds qubit count",
        }
    logical_qubits = qubit_count - rank
    degeneracy = 1 << logical_qubits
    return {
        "status": "ok",
        "task": "pauli_stabilizer_rank",
        "observable": request.get(
            "observable", "ground_state_degeneracy"
        ),
        "units": request.get("units", "states"),
        "value": degeneracy,
        "qubit_count": qubit_count,
        "generator_count": len(rows),
        "stabilizer_rank": rank,
        "logical_qubit_count": logical_qubits,
        "maximum_symplectic_commutator": maximum_commutator,
    }


def _ising_strip_transfer_entropy(product_result, request):
    if not isinstance(product_result, Mapping) or product_result.get(
        "status"
    ) != "ok":
        return {
            "status": "blocked",
            "task": "ising_strip_transfer_entropy",
            "blocker": "model simplification did not complete",
        }
    canonical = product_result.get("canonical_model", {})
    normalized = product_result.get("normalized_model", {})
    structure = normalized.get("lattice_structure", {})
    basis_count = len(structure.get("basis_sites", []))
    term_orbit_map = request.get("term_orbit_map")
    cell_widths = request.get("strip_cell_widths")
    inverse_temperatures = request.get("inverse_temperatures")
    if (
        normalized.get("lattice", {}).get("dimension") != 2
        or basis_count < 1
        or not isinstance(term_orbit_map, Mapping)
        or not term_orbit_map
        or not isinstance(cell_widths, (tuple, list))
        or len(cell_widths) < 4
        or any(
            isinstance(width, bool)
            or not isinstance(width, int)
            or width <= 0
            or width * basis_count > 12
            for width in cell_widths
        )
        or not isinstance(inverse_temperatures, (tuple, list))
        or len(inverse_temperatures) != 2
    ):
        return {
            "status": "invalid_request",
            "task": "ising_strip_transfer_entropy",
            "blocker": "analysis requires a 2D binary strip with four widths up to 12 sites",
        }
    try:
        beta_one, beta_two = (
            float(value) for value in inverse_temperatures
        )
    except (TypeError, ValueError):
        beta_one = beta_two = math.nan
    if (
        not math.isfinite(beta_one)
        or not math.isfinite(beta_two)
        or beta_one <= 0.0
        or beta_two <= beta_one
    ):
        return {
            "status": "invalid_request",
            "task": "ising_strip_transfer_entropy",
            "blocker": "inverse temperatures must be increasing and positive",
        }
    terms_by_block = {
        term.get("block_kind"): term
        for term in canonical.get("two_body", [])
    }
    orbit_by_ref = {
        orbit.get("orbit_ref"): orbit
        for orbit in structure.get("bond_orbits", [])
        if isinstance(orbit, Mapping)
    }
    horizontal_bonds = []
    vertical_bonds = []
    for block_kind, orbit_ref in term_orbit_map.items():
        term = terms_by_block.get(block_kind)
        orbit = orbit_by_ref.get(orbit_ref)
        try:
            coupling = float(term.get("coefficient")) / 4.0
        except (AttributeError, TypeError, ValueError):
            coupling = math.nan
        if (
            term is None
            or term.get("canonical_label") != "Sz@0 Sz@1"
            or orbit is None
            or not math.isfinite(coupling)
        ):
            return {
                "status": "unsupported",
                "task": "ising_strip_transfer_entropy",
                "blocker": "each strip orbit requires one finite SzSz block",
            }
        for member in orbit.get("members", []):
            source = member.get("source")
            target = member.get("target")
            translation = member.get("translation")
            if (
                not isinstance(source, int)
                or isinstance(source, bool)
                or not isinstance(target, int)
                or isinstance(target, bool)
                or not 0 <= source < basis_count
                or not 0 <= target < basis_count
                or not isinstance(translation, (tuple, list))
                or len(translation) < 2
                or translation[1] not in {0, 1}
            ):
                return {
                    "status": "unsupported",
                    "task": "ising_strip_transfer_entropy",
                    "blocker": "strip bonds must be intra-row or next-row bonds",
                }
            bond = (source, target, int(translation[0]), coupling)
            (horizontal_bonds if translation[1] == 0 else vertical_bonds).append(bond)
    if not horizontal_bonds or not vertical_bonds:
        return {
            "status": "unsupported",
            "task": "ising_strip_transfer_entropy",
            "blocker": "strip requires both horizontal and vertical bonds",
        }

    width_estimates = []
    for cell_width in cell_widths:
        site_width = cell_width * basis_count
        state_count = 1 << site_width
        states = np.asarray(
            [
                [1.0 if mask & (1 << site) else -1.0 for site in range(site_width)]
                for mask in range(state_count)
            ]
        )
        horizontal_energy = np.zeros(state_count)
        for source, target, shift, coupling in horizontal_bonds:
            for cell in range(cell_width):
                left = cell * basis_count + source
                right = ((cell + shift) % cell_width) * basis_count + target
                horizontal_energy += coupling * states[:, left] * states[:, right]
        vertical_energy = np.zeros((state_count, state_count))
        for source, target, shift, coupling in vertical_bonds:
            for cell in range(cell_width):
                old_index = cell * basis_count + source
                new_index = ((cell + shift) % cell_width) * basis_count + target
                vertical_energy += coupling * np.outer(
                    states[:, old_index], states[:, new_index]
                )
        transfer_energy = vertical_energy + horizontal_energy[None, :]
        minimum_entry = float(np.min(transfer_energy))
        log_eigenvalues = []
        for beta in (beta_one, beta_two):
            transfer = np.exp(
                -beta * (transfer_energy - minimum_entry)
            )
            vector = np.ones(state_count) / math.sqrt(state_count)
            eigenvalue = 0.0
            for _iteration in range(80):
                multiplied = transfer @ vector
                eigenvalue = float(np.linalg.norm(multiplied))
                vector = multiplied / eigenvalue
            log_eigenvalues.append(
                -beta * minimum_entry + math.log(eigenvalue)
            )
        entropy_per_row = (
            beta_two * log_eigenvalues[0]
            - beta_one * log_eigenvalues[1]
        ) / (beta_two - beta_one)
        width_estimates.append(
            {
                "cell_width": cell_width,
                "site_width": site_width,
                "entropy_per_spin": entropy_per_row / site_width,
            }
        )
    widths = np.asarray(
        [row["site_width"] for row in width_estimates], dtype=float
    )
    entropies = np.asarray(
        [row["entropy_per_spin"] for row in width_estimates], dtype=float
    )
    fit_all = np.polyfit(1.0 / widths[-4:] ** 2, entropies[-4:], 2)
    fit_last = np.polyfit(1.0 / widths[-3:] ** 2, entropies[-3:], 2)
    value = float(fit_all[-1])
    fit_stability = abs(value - float(fit_last[-1]))
    observable = request.get("observable", "residual_entropy_per_spin")
    observable_value = (
        value > fit_stability
        if observable == "macroscopic_ground_state_degeneracy"
        else value
    )
    return {
        "status": "ok",
        "task": "ising_strip_transfer_entropy",
        "observable": observable,
        "units": request.get("units", "k_B/spin"),
        "value": observable_value,
        "residual_entropy_per_spin": value,
        "width_estimates": width_estimates,
        "fit_stability_difference": fit_stability,
        "extrapolation_variable": "inverse_site_width_squared",
    }


def run_model_analysis(product_result, analysis_request):
    """Run a reusable analysis selected by its model-level task."""

    request = analysis_request if isinstance(analysis_request, Mapping) else {}
    task = request.get("task")
    if task == "local_spectrum":
        return _local_spectrum(product_result, request)
    if task == "spin_one_bilinear_biquadratic_decomposition":
        return _spin_one_bilinear_biquadratic_decomposition(
            product_result, request
        )
    if task == "one_dimensional_transfer_matrix":
        return _one_dimensional_transfer_matrix(product_result, request)
    if task == "classical_sz_enumeration":
        return _classical_sz_enumeration(product_result, request)
    if task == "local_constraint_entropy_estimate":
        return _local_constraint_entropy_estimate(product_result, request)
    if task == "periodic_classical_sz_enumeration":
        return _periodic_classical_sz_enumeration(product_result, request)
    if task == "finite_cluster_ed":
        return _finite_cluster_ed(product_result, request)
    if task == "ising_chain_free_fermion":
        return _ising_chain_free_fermion(product_result, request)
    if task == "xx_chain_free_fermion":
        return _xx_chain_free_fermion(product_result, request)
    if task == "xy_chain_free_fermion_boundaries":
        return _xy_chain_free_fermion_boundaries(product_result, request)
    if task == "xxx_chain_bethe_integral":
        return _xxx_chain_bethe_integral(product_result, request)
    if task == "fourier_exchange_spectrum":
        return _fourier_exchange_spectrum(product_result, request)
    if task == "bravais_fourier_competing_order_boundary":
        return _bravais_fourier_competing_order_boundary(
            product_result, request
        )
    if task == "fourier_curvature_instability_boundary":
        return _fourier_curvature_instability_boundary(
            product_result, request
        )
    if task == "kitaev_majorana_field_gap":
        return _kitaev_majorana_field_gap(product_result, request)
    if task == "pauli_stabilizer_rank":
        return _pauli_stabilizer_rank(product_result, request)
    if task == "ising_strip_transfer_entropy":
        return _ising_strip_transfer_entropy(product_result, request)
    if task == "scalar_root":
        return _scalar_root(product_result, request)
    return {
        "status": "unsupported",
        "task": task,
        "blocker": f"unsupported model analysis task: {task}",
    }
