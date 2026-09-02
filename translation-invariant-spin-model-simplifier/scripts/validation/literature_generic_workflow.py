"""Literature cases that exercise the generic model workflow.

Paper claims are deliberately separate from the answer-free model input sent
to product code.  This module belongs to validation/audit infrastructure; it
is not a product model router.
"""

from collections import Counter
from collections.abc import Mapping
import csv
from dataclasses import dataclass
import math
from pathlib import Path
from types import MappingProxyType


class LiteratureWorkflowContractError(ValueError):
    """Raised when a literature workflow record is not well formed."""


_INPUT_ROUTES = frozenset(
    {
        "natural_language",
        "operator",
        "matrix",
        "structured",
        "document",
        "many_body_hr",
    }
)


def _nonempty_text(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise LiteratureWorkflowContractError(
            f"{field_name} must be a nonempty string"
        )
    return value


def _freeze_json(value, field_name):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise LiteratureWorkflowContractError(
                f"{field_name} contains a non-finite number"
            )
        return value
    if isinstance(value, Mapping):
        frozen = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise LiteratureWorkflowContractError(
                    f"{field_name} contains a non-string key"
                )
            frozen[key] = _freeze_json(item, field_name)
        return MappingProxyType(frozen)
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_json(item, field_name) for item in value)
    raise LiteratureWorkflowContractError(
        f"{field_name} contains unsupported value {type(value).__name__}"
    )


def _frozen_mapping(value, field_name):
    if not isinstance(value, Mapping):
        raise LiteratureWorkflowContractError(
            f"{field_name} must be a mapping"
        )
    return _freeze_json(value, field_name)


@dataclass(frozen=True)
class LiteratureModelCase:
    """Answer-free input used to exercise the generic product workflow."""

    case_id: str
    source_id: str
    claim_id: str
    input_route: str
    model_input: Mapping
    analysis_request: Mapping

    def __post_init__(self):
        for field_name in ("case_id", "source_id", "claim_id"):
            _nonempty_text(getattr(self, field_name), field_name)
        if self.input_route not in _INPUT_ROUTES:
            raise LiteratureWorkflowContractError(
                "input_route is not supported by the literature workflow"
            )
        object.__setattr__(
            self,
            "model_input",
            _frozen_mapping(self.model_input, "model_input"),
        )
        object.__setattr__(
            self,
            "analysis_request",
            _frozen_mapping(self.analysis_request, "analysis_request"),
        )


@dataclass(frozen=True)
class LiteratureClaim:
    """Paper-side expected result, consumed only after product execution."""

    claim_id: str
    observable: str
    value: object
    uncertainty: float
    units: str
    source_location: str

    def __post_init__(self):
        for field_name in (
            "claim_id",
            "observable",
            "units",
            "source_location",
        ):
            _nonempty_text(getattr(self, field_name), field_name)
        if (
            isinstance(self.uncertainty, bool)
            or not isinstance(self.uncertainty, (int, float))
            or not math.isfinite(float(self.uncertainty))
            or self.uncertainty < 0
        ):
            raise LiteratureWorkflowContractError(
                "uncertainty must be a finite nonnegative number"
            )
        object.__setattr__(
            self, "value", _freeze_json(self.value, "claim value")
        )


def _thaw_json(value):
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def run_literature_case(case):
    """Run one answer-free case through the generic product workflow."""

    if not isinstance(case, LiteratureModelCase):
        raise LiteratureWorkflowContractError(
            "case must be a LiteratureModelCase"
        )

    from cli.simplify_text_input import (
        run_simplification_from_normalized_model,
        run_text_simplification_pipeline,
    )
    from input.normalize_input import normalize_input

    model_input = _thaw_json(case.model_input)
    if case.input_route in {"natural_language", "document"}:
        text = model_input.pop("text", None)
        if not isinstance(text, str) or not text.strip():
            raise LiteratureWorkflowContractError(
                "text input routes require model_input.text"
            )
        product_result = run_text_simplification_pipeline(
            text,
            **model_input,
        )
        normalized_model = product_result.get("normalized_model", {})
    elif case.input_route in {"operator", "matrix", "structured"}:
        normalized_model = normalize_input(model_input)
        product_result = run_simplification_from_normalized_model(
            normalized_model
        )
    else:
        return {
            "case_id": case.case_id,
            "source_id": case.source_id,
            "claim_id": case.claim_id,
            "normalization_status": "unsupported",
            "simplification_status": "not_run",
            "analysis_status": "not_run",
            "blocker": f"unsupported input route: {case.input_route}",
            "product_result": None,
        }

    product_status = product_result.get("status")
    normalization_status = (
        "needs_input"
        if product_status == "needs_input"
        else "completed"
    )
    simplification_status = (
        "completed"
        if product_status == "ok"
        else product_status or "failed"
    )
    requested_task = case.analysis_request.get("task")
    analysis_result = None
    if requested_task in {None, "simplification"}:
        analysis_status = "not_requested"
    elif product_status != "ok":
        analysis_status = "not_run"
    else:
        from common.model_analysis import run_model_analysis

        analysis_result = run_model_analysis(
            product_result,
            _thaw_json(case.analysis_request),
        )
        analysis_status = (
            "completed"
            if analysis_result.get("status") == "ok"
            else analysis_result.get("status", "failed")
        )
    return {
        "case_id": case.case_id,
        "source_id": case.source_id,
        "claim_id": case.claim_id,
        "normalization_status": normalization_status,
        "simplification_status": simplification_status,
        "analysis_status": analysis_status,
        "analysis_result": analysis_result,
        "normalized_model": normalized_model,
        "product_result": product_result,
    }


def _numeric_differences(computed, expected):
    if (
        not isinstance(computed, bool)
        and not isinstance(expected, bool)
        and isinstance(computed, (int, float))
        and isinstance(expected, (int, float))
    ):
        if not math.isfinite(float(computed)):
            return None
        return [abs(float(computed) - float(expected))]
    if isinstance(computed, Mapping) and isinstance(expected, Mapping):
        if set(computed) != set(expected):
            return None
        differences = []
        for key in sorted(computed):
            item_differences = _numeric_differences(
                computed[key], expected[key]
            )
            if item_differences is None:
                return None
            differences.extend(item_differences)
        return differences
    if isinstance(computed, (tuple, list)) and isinstance(
        expected, (tuple, list)
    ):
        if len(computed) != len(expected):
            return None
        differences = []
        for computed_item, expected_item in zip(computed, expected):
            item_differences = _numeric_differences(
                computed_item, expected_item
            )
            if item_differences is None:
                return None
            differences.extend(item_differences)
        return differences
    return [] if computed == expected else None


def compare_literature_claim(computed_observable, claim):
    """Compare a completed product observable with a paper-side claim."""

    if not isinstance(claim, LiteratureClaim):
        raise LiteratureWorkflowContractError(
            "claim must be a LiteratureClaim"
        )
    if not isinstance(computed_observable, Mapping):
        raise LiteratureWorkflowContractError(
            "computed observable must be a mapping"
        )
    if computed_observable.get("observable") != claim.observable:
        return {
            "status": "inconclusive",
            "reason": "observable mismatch",
        }
    if computed_observable.get("units") != claim.units:
        return {
            "status": "inconclusive",
            "reason": "units mismatch",
        }

    differences = _numeric_differences(
        computed_observable.get("value"), claim.value
    )
    if differences is None:
        return {
            "status": "mismatched",
            "reason": "value shape or content mismatch",
            "maximum_absolute_difference": None,
        }
    maximum_difference = max(differences, default=0.0)
    return {
        "status": (
            "matched"
            if maximum_difference <= float(claim.uncertainty)
            else "mismatched"
        ),
        "maximum_absolute_difference": maximum_difference,
        "allowed_absolute_difference": float(claim.uncertainty),
    }


def build_eligible_workflow_inventory(cases, *, claims=()):
    """Run migrated cases and expose honest layered status for all eligible models."""

    from validation import literature_evidence_adapters as adapters

    case_by_id = {}
    for case in cases:
        if not isinstance(case, LiteratureModelCase):
            raise LiteratureWorkflowContractError(
                "inventory cases must be LiteratureModelCase records"
            )
        if case.case_id in case_by_id:
            raise LiteratureWorkflowContractError(
                f"duplicate literature case id: {case.case_id}"
            )
        case_by_id[case.case_id] = case

    claim_by_id = {}
    for claim in claims:
        if not isinstance(claim, LiteratureClaim):
            raise LiteratureWorkflowContractError(
                "inventory claims must be LiteratureClaim records"
            )
        if claim.claim_id in claim_by_id:
            raise LiteratureWorkflowContractError(
                f"duplicate literature claim id: {claim.claim_id}"
            )
        claim_by_id[claim.claim_id] = claim

    rows = []
    for model_id, eligibility in adapters.ADAPTER_ELIGIBILITY.items():
        if eligibility.disposition != "eligible":
            continue
        definition = adapters.ADAPTER_DEFINITIONS[eligibility.adapter_id]
        case = case_by_id.get(model_id)
        if case is None:
            rows.append(
                {
                    "model_id": model_id,
                    "source_id": None,
                    "claim_id": None,
                    "input_route": None,
                    "adapter_backend_kind": definition.backend_kind,
                    "analysis_kind": None,
                    "migration_status": "not_migrated",
                    "normalization_status": "not_run",
                    "simplification_status": "not_run",
                    "backend_status": "not_run",
                    "analysis_status": "not_run",
                    "computation_status": "not_run",
                    "convergence_status": "not_run",
                    "oracle_status": "not_connected",
                    "literature_match_status": "not_run",
                    "blocker": "answer-free generic model input not yet migrated",
                }
            )
            continue

        result = run_literature_case(case)
        analysis_result = result.get("analysis_result") or {}
        analysis_status = result["analysis_status"]
        claim = claim_by_id.get(case.claim_id)
        match_status = "not_run"
        if analysis_status == "completed" and claim is not None:
            comparison = compare_literature_claim(analysis_result, claim)
            match_status = comparison["status"]
        backend_status = (
            "available"
            if analysis_status in {"completed", "inconclusive"}
            else (
                "not_requested"
                if analysis_status == "not_requested"
                else analysis_status
            )
        )
        computation_status = (
            analysis_status
            if analysis_status in {
                "completed",
                "inconclusive",
                "not_requested",
            }
            else "not_run"
        )
        rows.append(
            {
                "model_id": model_id,
                "source_id": case.source_id,
                "claim_id": case.claim_id,
                "input_route": case.input_route,
                "adapter_backend_kind": definition.backend_kind,
                "analysis_kind": case.analysis_request.get("task"),
                "migration_status": "migrated",
                "normalization_status": result["normalization_status"],
                "simplification_status": result["simplification_status"],
                "backend_status": backend_status,
                "analysis_status": analysis_status,
                "computation_status": computation_status,
                "convergence_status": _convergence_status(
                    analysis_status, analysis_result
                ),
                "oracle_status": "not_connected",
                "literature_match_status": match_status,
                "blocker": (
                    None
                    if analysis_status
                    in {"completed", "not_requested"}
                    else (
                        result.get("analysis_result") or {}
                    ).get("blocker", result["analysis_status"])
                ),
            }
        )
    return tuple(rows)


_CONVERGENCE_EVIDENCE_FIELDS = frozenset(
    {
        "bracket_width",
        "critical_gap_residual",
        "curvature_residual",
        "directional_projector_difference",
        "dirac_residual",
        "energy_crossing_residual",
        "fit_stability_difference",
        "flat_band_width",
        "ratio_bracket_width",
        "reconstruction_residual",
        "reference_energy_difference",
        "refinement_difference",
        "residual",
        "varied_energy_difference",
        "width_estimates",
    }
)


def _registered_case_maps(cases, claims, registry_names):
    case_by_id = {}
    for case in cases:
        if not isinstance(case, LiteratureModelCase):
            raise LiteratureWorkflowContractError(
                "registered inventory cases must be LiteratureModelCase records"
            )
        if case.case_id in case_by_id:
            raise LiteratureWorkflowContractError(
                f"duplicate literature case id: {case.case_id}"
            )
        if case.case_id not in registry_names:
            raise LiteratureWorkflowContractError(
                f"literature case is absent from the registry: {case.case_id}"
            )
        case_by_id[case.case_id] = case

    claim_by_id = {}
    for claim in claims:
        if not isinstance(claim, LiteratureClaim):
            raise LiteratureWorkflowContractError(
                "registered inventory claims must be LiteratureClaim records"
            )
        if claim.claim_id in claim_by_id:
            raise LiteratureWorkflowContractError(
                f"duplicate literature claim id: {claim.claim_id}"
            )
        claim_by_id[claim.claim_id] = claim
    return case_by_id, claim_by_id


def _convergence_status(analysis_status, analysis_result):
    if analysis_status == "inconclusive":
        return "not_demonstrated"
    if analysis_status != "completed":
        return "not_run"
    if _CONVERGENCE_EVIDENCE_FIELDS.intersection(analysis_result):
        return "satisfied"
    return "not_applicable"


def build_registered_workflow_inventory(
    *, registry_entries=None, cases=(), claims=()
):
    """Describe all registered claims without feeding paper answers to product code.

    Registry metadata identifies the source, model, observable, and requested
    backend family.  Only an explicitly migrated ``LiteratureModelCase`` is
    executed.  In particular, this function never reads ``standard_result``.
    """

    from validation.literature_evidence_inventory import (
        canonical_source_identity,
        source_id_for_identity,
    )

    if registry_entries is None:
        from validation.literature_spin_model_benchmarks import (
            LITERATURE_STANDARD_RESULTS,
        )

        registry_entries = LITERATURE_STANDARD_RESULTS

    registry = tuple(registry_entries)
    registry_names = tuple(entry.get("name") for entry in registry)
    if len(registry_names) != 155 or len(set(registry_names)) != 155:
        raise LiteratureWorkflowContractError(
            "registered workflow inventory requires 155 unique benchmark names"
        )
    registry_name_set = frozenset(registry_names)
    case_by_id, claim_by_id = _registered_case_maps(
        cases, claims, registry_name_set
    )

    identities = tuple(
        canonical_source_identity(entry.get("source_url"))
        for entry in registry
    )
    if len(set(identities)) != 137:
        raise LiteratureWorkflowContractError(
            "registered workflow inventory requires 137 canonical sources"
        )

    rows = []
    for entry, source_identity in sorted(
        zip(registry, identities), key=lambda item: item[0]["name"]
    ):
        benchmark_name = entry["name"]
        case = case_by_id.get(benchmark_name)
        base = {
            "benchmark_name": benchmark_name,
            "canonical_source_identity": source_identity,
            "source_id": source_id_for_identity(source_identity),
            "model": entry.get("model"),
            "lattice": entry.get("lattice"),
            "observable": entry.get("observable"),
            "comparison_kind": entry.get("comparison_kind"),
            "registry_backend_needed": entry.get("backend_needed"),
        }
        if case is None:
            rows.append(
                {
                    **base,
                    "input_route": None,
                    "analysis_kind": None,
                    "model_input_status": "not_landed",
                    "claim_extraction_status": "not_extracted",
                    "migration_status": "not_landed",
                    "normalization_status": "not_run",
                    "simplification_status": "not_run",
                    "analysis_status": "not_run",
                    "convergence_status": "not_run",
                    "oracle_status": "not_connected",
                    "literature_match_status": "not_run",
                    "blocker": "answer-free generic model input not yet landed",
                }
            )
            continue

        result = run_literature_case(case)
        analysis_result = result.get("analysis_result") or {}
        analysis_status = result["analysis_status"]
        claim = claim_by_id.get(case.claim_id)
        if analysis_status == "inconclusive":
            match_status = "inconclusive"
        elif analysis_status == "completed" and claim is not None:
            match_status = compare_literature_claim(
                analysis_result, claim
            )["status"]
        else:
            match_status = "not_run"
        blocker = None
        if analysis_status not in {"completed", "not_requested"}:
            blocker = analysis_result.get(
                "blocker", "analysis did not complete"
            )
        rows.append(
            {
                **base,
                "input_route": case.input_route,
                "analysis_kind": case.analysis_request.get("task"),
                "model_input_status": "answer_free_ready",
                "claim_extraction_status": (
                    "extracted" if claim is not None else "not_extracted"
                ),
                "migration_status": "migrated",
                "normalization_status": result["normalization_status"],
                "simplification_status": result["simplification_status"],
                "analysis_status": analysis_status,
                "convergence_status": _convergence_status(
                    analysis_status, analysis_result
                ),
                "oracle_status": "not_connected",
                "literature_match_status": match_status,
                "blocker": blocker,
            }
        )
    return tuple(rows)


def _lattice_with_explicit_bond_orbit(lattice):
    lattice_payload = dict(lattice)
    representative = dict(lattice_payload.pop("representative"))
    members = [
        {
            **dict(member),
            "generated_by_operation_ref": "explicit",
        }
        for member in lattice_payload.pop("members")
    ]
    lattice_payload["bond_orbits"] = [
        {
            "orbit_ref": "bond-orbit:1",
            "kind": "pair",
            "directed": False,
            "orientation_convention": "undirected",
            "source_labels": ["1"],
            "shell": 1,
            "representative": representative,
            "members": members,
            "reverse_orientation": {
                "kind": "same_undirected_bond",
                "source_target_swap": True,
                "transpose": False,
                "translation": [
                    -int(value)
                    for value in representative["translation"]
                ],
            },
            "selection_aliases": ["1"],
        }
    ]
    return lattice_payload


def _classical_ising_critical_case(
    *, case_id, source_id, claim_id, lattice, equation
):
    lattice_payload = _lattice_with_explicit_bond_orbit(lattice)
    return LiteratureModelCase(
        case_id=case_id,
        source_id=source_id,
        claim_id=claim_id,
        input_route="structured",
        model_input={
            "representation": "operator",
            "support": [0, 1],
            "expression": "-J*(4*Sz@0 Sz@1)",
            "parameters": {"J": 1.0},
            "local_dim": 2,
            "lattice": lattice_payload,
            "classical_bond_label": "spin-only",
            "selected_local_bond_bond_label": "1",
        },
        analysis_request={
            "task": "scalar_root",
            "variable": "T",
            "equation": equation,
            "parameters": {"J": 1.0},
            "bracket": [0.1, 10.0],
            "absolute_tolerance": 1.0e-12,
            "observable": "critical_temperature",
            "units": "J/k_B",
        },
    )


def _classical_ising_entropy_case(
    *, case_id, source_id, claim_id, lattice, supercells
):
    return LiteratureModelCase(
        case_id=case_id,
        source_id=source_id,
        claim_id=claim_id,
        input_route="structured",
        model_input={
            "representation": "operator",
            "support": [0, 1],
            "expression": "J*(4*Sz@0 Sz@1)",
            "parameters": {"J": 1.0},
            "local_dim": 2,
            "lattice": _lattice_with_explicit_bond_orbit(lattice),
            "classical_bond_label": "spin-only",
            "selected_local_bond_bond_label": "1",
        },
        analysis_request={
            "task": "periodic_classical_sz_enumeration",
            "bond_orbit_ref": "bond-orbit:1",
            "supercells": supercells,
            "require_thermodynamic_limit": True,
            "observable": "residual_entropy_per_spin",
            "units": "k_B/spin",
        },
    )


def _pyrochlore_pauling_case():
    return LiteratureModelCase(
        case_id="pyrochlore_dipolar_spin_ice_pauling_entropy",
        source_id="Bramwell_Gingras_2001",
        claim_id="pyrochlore_pauling_entropy_per_spin",
        input_route="structured",
        model_input={
            "representation": "operator",
            "support": [0, 1],
            "expression": "J*(4*Sz@0 Sz@1)",
            "parameters": {"J": 1.0},
            "local_dim": 2,
            "lattice": _lattice_with_explicit_bond_orbit(
                {
                    "kind": "pyrochlore_tetrahedron_constraint",
                    "dimension": 3,
                    "positions": [
                        [0.0, 0.0, 0.0],
                        [0.0, 0.5, 0.5],
                        [0.5, 0.0, 0.5],
                        [0.5, 0.5, 0.0],
                    ],
                    "lattice_vectors": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                    ],
                    "representative": {
                        "source": 0,
                        "target": 1,
                        "translation": [0, 0, 0],
                    },
                    "members": [
                        {
                            "source": left,
                            "target": right,
                            "translation": [0, 0, 0],
                        }
                        for left, right in (
                            (0, 1), (0, 2), (0, 3),
                            (1, 2), (1, 3), (2, 3),
                        )
                    ],
                }
            ),
            "classical_bond_label": "spin-only",
            "selected_local_bond_bond_label": "1",
        },
        analysis_request={
            "task": "local_constraint_entropy_estimate",
            "bond_orbit_ref": "bond-orbit:1",
            "constraints_per_site": 0.5,
            "observable": "pauling_entropy_per_spin",
            "units": "k_B/spin",
        },
    )


def _pyrochlore_heisenberg_case():
    edges = (
        (0, 1, (-1, 0, 0)), (0, 1, (0, 0, 0)),
        (0, 2, (0, -1, 0)), (0, 2, (0, 0, 0)),
        (0, 3, (0, 0, -1)), (0, 3, (0, 0, 0)),
        (1, 2, (0, 0, 0)), (1, 2, (1, -1, 0)),
        (1, 3, (0, 0, 0)), (1, 3, (1, 0, -1)),
        (2, 3, (0, 0, 0)), (2, 3, (0, 1, -1)),
    )
    return LiteratureModelCase(
        case_id="pyrochlore_heisenberg_afm_coulomb_phase_reference",
        source_id="Moessner_Chalker_1998",
        claim_id="pyrochlore_coulomb_constraint",
        input_route="structured",
        model_input={
            "representation": "operator",
            "support": [0, 1],
            "expression": "J*(Sx@0 Sx@1 + Sy@0 Sy@1 + Sz@0 Sz@1)",
            "parameters": {"J": 1.0},
            "local_dim": 2,
            "lattice": {
                "kind": "pyrochlore",
                "dimension": 3,
                "positions": [
                    [0.0, 0.0, 0.0],
                    [0.0, 0.25, 0.25],
                    [0.25, 0.0, 0.25],
                    [0.25, 0.25, 0.0],
                ],
                "lattice_vectors": [
                    [0.0, 0.5, 0.5],
                    [0.5, 0.0, 0.5],
                    [0.5, 0.5, 0.0],
                ],
                "bond_orbits": [
                    {
                        "orbit_ref": "bond-orbit:J1",
                        "kind": "pair",
                        "directed": False,
                        "orientation_convention": "undirected",
                        "source_labels": ["J1"],
                        "shell": 1,
                        "representative": {
                            "source": 0,
                            "target": 1,
                            "translation": [0, 0, 0],
                        },
                        "members": [
                            {
                                "source": source,
                                "target": target,
                                "translation": list(translation),
                                "generated_by_operation_ref": "explicit",
                            }
                            for source, target, translation in edges
                        ],
                        "reverse_orientation": {
                            "kind": "same_undirected_bond",
                            "source_target_swap": True,
                            "transpose": False,
                            "translation": [0, 0, 0],
                        },
                        "selection_aliases": ["J1"],
                    }
                ],
            },
            "classical_bond_label": "spin-only",
            "selected_local_bond_bond_label": "J1",
        },
        analysis_request={
            "task": "fourier_exchange_spectrum",
            "term_orbit_map": {"default": "bond-orbit:J1"},
            "reduced_momenta": [
                [0.001, 0.0, 0.0],
                [0.0, 0.001, 0.0],
                [0.0, 0.0, 0.001],
                [0.13, 0.27, 0.31],
            ],
            "flat_band_count": 2,
            "observable": "flat_band_constraint_summary",
            "units": "dimensionless",
        },
    )


def _simple_cubic_j1_j2_case():
    orbit_members = {
        "J1": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
        "J2": (
            (1, 1, 0), (1, -1, 0),
            (1, 0, 1), (1, 0, -1),
            (0, 1, 1), (0, 1, -1),
        ),
    }
    return LiteratureModelCase(
        case_id="simple_cubic_j1_j2_collinear_reference",
        source_id="Pinettes_Diep_1998",
        claim_id="simple_cubic_neel_collinear_boundary",
        input_route="structured",
        model_input={
            "representation": "operator_channel_collection",
            "support": [0, 1],
            "expressions": [
                {
                    "block_kind": block,
                    "expression": (
                        f"{block}*(Sx@0 Sx@1 + Sy@0 Sy@1 + Sz@0 Sz@1)"
                    ),
                }
                for block in ("J1", "J2")
            ],
            "parameters": {"J1": 1.0, "J2": 0.3},
            "local_dim": 2,
            "lattice": {
                "kind": "simple_cubic",
                "dimension": 3,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                "bond_orbits": [
                    {
                        "orbit_ref": f"bond-orbit:{block}",
                        "kind": "pair",
                        "directed": False,
                        "orientation_convention": "undirected",
                        "source_labels": [block],
                        "shell": index,
                        "representative": {
                            "source": 0,
                            "target": 0,
                            "translation": list(vectors[0]),
                        },
                        "members": [
                            {
                                "source": 0,
                                "target": 0,
                                "translation": list(vector),
                                "generated_by_operation_ref": "explicit",
                            }
                            for vector in vectors
                        ],
                        "reverse_orientation": {
                            "kind": "same_undirected_bond",
                            "source_target_swap": True,
                            "transpose": False,
                            "translation": [-value for value in vectors[0]],
                        },
                        "selection_aliases": [block],
                    }
                    for index, (block, vectors) in enumerate(
                        orbit_members.items(), start=1
                    )
                ],
            },
            "classical_bond_label": "spin-only",
            "selected_local_bond_bond_label": "J1",
        },
        analysis_request={
            "task": "bravais_fourier_competing_order_boundary",
            "term_orbit_map": {
                "J1": "bond-orbit:J1",
                "J2": "bond-orbit:J2",
            },
            "reference_block": "J1",
            "varied_block": "J2",
            "competing_momenta": [
                [0.5, 0.5, 0.5],
                [0.5, 0.5, 0.0],
            ],
            "observable": "neel_to_collinear_boundary_j2_over_j1",
            "units": "J2/J1",
        },
    )


def _diamond_j1_j2_case():
    nearest = (
        (0, 1, (-1, 0, 0)), (0, 1, (0, -1, 0)),
        (0, 1, (0, 0, -1)), (0, 1, (0, 0, 0)),
    )
    next_vectors = (
        (-1, 0, 0), (-1, 0, 1), (-1, 1, 0),
        (0, -1, 0), (0, -1, 1), (0, 0, -1),
    )
    next_nearest = tuple(
        (site, site, vector) for site in (0, 1) for vector in next_vectors
    )
    orbit_members = {"J1": nearest, "J2": next_nearest}
    return LiteratureModelCase(
        case_id="diamond_j1_j2_spiral_surface_reference",
        source_id="Bergman_Alicea_Gull_Trebst_Balents_2007",
        claim_id="diamond_spiral_surface_threshold",
        input_route="structured",
        model_input={
            "representation": "operator_channel_collection",
            "support": [0, 1],
            "expressions": [
                {
                    "block_kind": block,
                    "expression": (
                        f"{block}*(Sx@0 Sx@1 + Sy@0 Sy@1 + Sz@0 Sz@1)"
                    ),
                }
                for block in ("J1", "J2")
            ],
            "parameters": {"J1": 1.0, "J2": 0.15},
            "local_dim": 2,
            "lattice": {
                "kind": "diamond",
                "dimension": 3,
                "positions": [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
                "lattice_vectors": [
                    [0.0, 0.5, 0.5],
                    [0.5, 0.0, 0.5],
                    [0.5, 0.5, 0.0],
                ],
                "bond_orbits": [
                    {
                        "orbit_ref": f"bond-orbit:{block}",
                        "kind": "pair",
                        "directed": False,
                        "orientation_convention": "undirected",
                        "source_labels": [block],
                        "shell": index,
                        "representative": {
                            "source": members[0][0],
                            "target": members[0][1],
                            "translation": list(members[0][2]),
                        },
                        "members": [
                            {
                                "source": source,
                                "target": target,
                                "translation": list(translation),
                                "generated_by_operation_ref": "explicit",
                            }
                            for source, target, translation in members
                        ],
                        "reverse_orientation": {
                            "kind": "same_undirected_bond",
                            "source_target_swap": True,
                            "transpose": False,
                            "translation": [
                                -value for value in members[0][2]
                            ],
                        },
                        "selection_aliases": [block],
                    }
                    for index, (block, members) in enumerate(
                        orbit_members.items(), start=1
                    )
                ],
            },
            "classical_bond_label": "spin-only",
            "selected_local_bond_bond_label": "J1",
        },
        analysis_request={
            "task": "fourier_curvature_instability_boundary",
            "term_orbit_map": {
                "J1": "bond-orbit:J1",
                "J2": "bond-orbit:J2",
            },
            "reference_block": "J1",
            "varied_block": "J2",
            "central_momentum": [0.0, 0.0, 0.0],
            "momentum_displacement": [0.001, 0.0, 0.0],
            "ratio_bracket": [0.05, 0.2],
            "absolute_tolerance": 1.0e-10,
            "observable": "spiral_surface_for_j2_over_j1_gt",
            "units": "J2/J1",
        },
    )


def _kitaev_field_case():
    return LiteratureModelCase(
        case_id="kitaev_honeycomb_abelian_nonabelian_field_gap_reference",
        source_id="Kitaev_2006",
        claim_id="kitaev_field_opens_non_abelian_gap",
        input_route="structured",
        model_input={
            "representation": "operator_channel_collection",
            "support": [0, 1],
            "expressions": [
                {
                    "block_kind": f"{axis}_bond",
                    "expression": f"K{axis}*S{axis}@0 S{axis}@1",
                }
                for axis in ("x", "y", "z")
            ],
            "parameters": {"Kx": 1.0, "Ky": 1.0, "Kz": 1.0},
            "local_dim": 2,
            "lattice": {
                "kind": "honeycomb",
                "dimension": 2,
                "positions": [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                "lattice_vectors": [
                    [math.sqrt(3.0), 0.0, 0.0],
                    [math.sqrt(3.0) / 2.0, 1.5, 0.0],
                    [0.0, 0.0, 8.0],
                ],
                "bond_orbits": [
                    {
                        "orbit_ref": f"bond-orbit:{axis}",
                        "kind": "pair",
                        "directed": False,
                        "orientation_convention": "undirected",
                        "source_labels": [axis],
                        "shell": 1,
                        "representative": {
                            "source": 0,
                            "target": 1,
                            "translation": list(translation),
                        },
                        "members": [
                            {
                                "source": 0,
                                "target": 1,
                                "translation": list(translation),
                                "generated_by_operation_ref": "explicit",
                            }
                        ],
                        "reverse_orientation": {
                            "kind": "same_undirected_bond",
                            "source_target_swap": True,
                            "transpose": False,
                            "translation": [-value for value in translation],
                        },
                        "selection_aliases": [axis],
                    }
                    for axis, translation in (
                        ("x", (0, 0, 0)),
                        ("y", (-1, 0, 0)),
                        ("z", (0, -1, 0)),
                    )
                ],
            },
            "onsite_terms": [
                {
                    "kind": "linear_spin_cartesian",
                    "site_scope": {"kind": "site", "site": 0},
                    "operator_basis": {
                        "bond_label": "spin_cartesian",
                        "components": ["Sx", "Sy", "Sz"],
                    },
                    "frame": {
                        "kind": "global_cartesian",
                        "axes": ["x", "y", "z"],
                    },
                    "payload": {"vector": [-0.1, -0.08, -0.06]},
                    "provenance": {
                        "source_kind": "answer_free_model_input"
                    },
                }
            ],
            "classical_bond_label": "spin-only",
            "selected_local_bond_bond_label": "x",
        },
        analysis_request={
            "task": "kitaev_majorana_field_gap",
            "observable": "field_opens_non_abelian_gap",
            "units": "dimensionless",
        },
    )


def _toric_code_case():
    size = 2

    def horizontal(x, y):
        return y * size + x

    def vertical(x, y):
        return size * size + y * size + x

    expressions = []
    for y in range(size):
        for x in range(size):
            star = (
                horizontal(x, y),
                horizontal((x - 1) % size, y),
                vertical(x, y),
                vertical(x, (y - 1) % size),
            )
            plaquette = (
                horizontal(x, y),
                vertical((x + 1) % size, y),
                horizontal(x, (y + 1) % size),
                vertical(x, y),
            )
            expressions.extend(
                (
                    {
                        "block_kind": f"star_{x}_{y}",
                        "expression": "-16*" + " ".join(
                            f"Sx@{site}" for site in star
                        ),
                    },
                    {
                        "block_kind": f"plaquette_{x}_{y}",
                        "expression": "-16*" + " ".join(
                            f"Sz@{site}" for site in plaquette
                        ),
                    },
                )
            )
    positions = []
    for y in range(size):
        for x in range(size):
            positions.append([x + 0.5, float(y), 0.0])
    for y in range(size):
        for x in range(size):
            positions.append([float(x), y + 0.5, 0.0])
    return LiteratureModelCase(
        case_id="square_toric_code_exact_topological_degeneracy",
        source_id="Kitaev_2003",
        claim_id="toric_code_torus_ground_state_degeneracy",
        input_route="structured",
        model_input={
            "representation": "operator_channel_collection",
            "support": list(range(8)),
            "expressions": expressions,
            "parameters": {},
            "local_dim": 2,
            "lattice": {
                "kind": "square_edge_qubits",
                "dimension": 2,
                "positions": positions,
                "lattice_vectors": [
                    [2.0, 0.0, 0.0],
                    [0.0, 2.0, 0.0],
                    [0.0, 0.0, 8.0],
                ],
            },
            "classical_bond_label": "spin-only",
            "selected_local_bond_bond_label": "1",
        },
        analysis_request={
            "task": "pauli_stabilizer_rank",
            "qubit_count": 8,
            "observable": "torus_ground_state_degeneracy",
            "units": "states",
        },
    )


def _fully_frustrated_square_ising_case():
    orbit_members = {
        "horizontal": (
            (0, 1, (0, 0, 0)),
            (1, 0, (1, 0, 0)),
        ),
        "vertical_even": ((0, 0, (0, 1, 0)),),
        "vertical_odd": ((1, 1, (0, 1, 0)),),
    }
    couplings = {
        "horizontal": -4.0,
        "vertical_even": -4.0,
        "vertical_odd": 4.0,
    }
    return LiteratureModelCase(
        case_id="square_fully_frustrated_ising_residual_entropy_reference",
        source_id="Villain_1977",
        claim_id="fully_frustrated_macroscopic_degeneracy",
        input_route="structured",
        model_input={
            "representation": "operator_channel_collection",
            "support": [0, 1],
            "expressions": [
                {
                    "block_kind": block,
                    "expression": f"{coefficient}*Sz@0 Sz@1",
                }
                for block, coefficient in couplings.items()
            ],
            "parameters": {},
            "local_dim": 2,
            "lattice": {
                "kind": "square_fully_frustrated",
                "dimension": 2,
                "positions": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                "lattice_vectors": [
                    [2.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 8.0],
                ],
                "bond_orbits": [
                    {
                        "orbit_ref": f"bond-orbit:{block}",
                        "kind": "pair",
                        "directed": False,
                        "orientation_convention": "undirected",
                        "source_labels": [block],
                        "shell": 1,
                        "representative": {
                            "source": members[0][0],
                            "target": members[0][1],
                            "translation": list(members[0][2]),
                        },
                        "members": [
                            {
                                "source": source,
                                "target": target,
                                "translation": list(translation),
                                "generated_by_operation_ref": "explicit",
                            }
                            for source, target, translation in members
                        ],
                        "reverse_orientation": {
                            "kind": "same_undirected_bond",
                            "source_target_swap": True,
                            "transpose": False,
                            "translation": [
                                -value for value in members[0][2]
                            ],
                        },
                        "selection_aliases": [block],
                    }
                    for block, members in orbit_members.items()
                ],
            },
            "classical_bond_label": "spin-only",
            "selected_local_bond_bond_label": "horizontal",
        },
        analysis_request={
            "task": "ising_strip_transfer_entropy",
            "term_orbit_map": {
                block: f"bond-orbit:{block}" for block in orbit_members
            },
            "strip_cell_widths": [3, 4, 5, 6],
            "inverse_temperatures": [15.0, 16.0],
            "observable": "macroscopic_ground_state_degeneracy",
            "units": "dimensionless",
        },
    )


def _spin_one_two_site_hilbert():
    return {
        "sites": [
            {
                "site_ref": f"site:{site}",
                "space_ref": "space:spin_s_1",
                "basis_ref": "basis:spin_s_1",
                "classical_space_ref": "classical_space:spin_unit_vector",
                "operator_basis_refs": ["op_basis:spin_cartesian"],
            }
            for site in (0, 1)
        ],
        "basis_registry": {
            "basis:spin_s_1": {
                "kind": "spin_multiplet",
                "dimension": 3,
                "basis_order": ["m=1", "m=0", "m=-1"],
            }
        },
        "operator_bases": {
            "op_basis:spin_cartesian": {
                "kind": "spin_cartesian",
                "basis_order": ["Sx", "Sy", "Sz"],
            }
        },
        "classical_spaces": {
            "classical_space:spin_unit_vector": {
                "kind": "unit_vector_sphere",
                "dimension": 3,
            }
        },
    }


def _spin_one_total_spin_two_projector():
    root_two = math.sqrt(2.0)
    root_six = math.sqrt(6.0)
    vectors = []
    for entries in (
        ((0, 1.0),),
        ((1, 1.0 / root_two), (3, 1.0 / root_two)),
        (
            (2, 1.0 / root_six),
            (4, 2.0 / root_six),
            (6, 1.0 / root_six),
        ),
        ((5, 1.0 / root_two), (7, 1.0 / root_two)),
        ((8, 1.0),),
    ):
        vector = [0.0] * 9
        for index, value in entries:
            vector[index] = value
        vectors.append(vector)
    return [
        [
            sum(vector[row] * vector[column] for vector in vectors)
            for column in range(9)
        ]
        for row in range(9)
    ]


def _spin_one_bilinear_biquadratic_matrix(
    bilinear, biquadratic, constant_shift=0.0
):
    dot_product = [[0.0] * 9 for _index in range(9)]
    magnetic_values = (1.0, 0.0, -1.0)
    for left in range(3):
        for right in range(3):
            index = 3 * left + right
            dot_product[index][index] = (
                magnetic_values[left] * magnetic_values[right]
            )
    for left, right in ((1, 3), (2, 4), (4, 6), (5, 7)):
        dot_product[left][right] = 1.0
        dot_product[right][left] = 1.0
    dot_squared = [
        [
            sum(
                dot_product[row][inner] * dot_product[inner][column]
                for inner in range(9)
            )
            for column in range(9)
        ]
        for row in range(9)
    ]
    return [
        [
            constant_shift * (row == column)
            + bilinear * dot_product[row][column]
            + biquadratic * dot_squared[row][column]
            for column in range(9)
        ]
        for row in range(9)
    ]


def _spin_one_chain_matrix_case(
    *, case_id, source_id, claim_id, matrix
):
    return LiteratureModelCase(
        case_id=case_id,
        source_id=source_id,
        claim_id=claim_id,
        input_route="matrix",
        model_input={
            "representation": "matrix",
            "support": [0, 1],
            "matrix": matrix,
            "local_dim": 3,
            "local_hilbert": _spin_one_two_site_hilbert(),
            "lattice": {
                "kind": "chain",
                "dimension": 1,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.0, 8.0, 0.0],
                    [0.0, 0.0, 8.0],
                ],
            },
            "classical_bond_label": "spin-only",
            "selected_local_bond_bond_label": "1",
        },
        analysis_request={
            "task": "spin_one_bilinear_biquadratic_decomposition",
            "observable": "coefficient_summary",
            "units": "dimensionless",
        },
    )


def initial_generic_literature_cases():
    """Return the first literature models migrated to generic product inputs."""

    return (
        LiteratureModelCase(
            case_id="xxx_spin_half_chain_bethe_ground_state",
            source_id="Bethe_1931",
            claim_id="thermodynamic_limit_ground_state_energy",
            input_route="structured",
            model_input={
                "representation": "operator",
                "support": [0, 1],
                "expression": (
                    "J*(Sx@0 Sx@1 + Sy@0 Sy@1 + Sz@0 Sz@1)"
                ),
                "parameters": {"J": 1.0},
                "local_dim": 2,
                "lattice": {
                    "kind": "chain",
                    "dimension": 1,
                    "positions": [[0.0, 0.0, 0.0]],
                    "lattice_vectors": [
                        [1.0, 0.0, 0.0],
                        [0.0, 8.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                    "bond_orbit_shell_map": {
                        "1": {"shell_index": 1, "distance": 1.0},
                    },
                    "bond_orbit_representative_map": {
                        "1": {
                            "source": 0,
                            "target": 0,
                            "translation": [1, 0, 0],
                        },
                    },
                },
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "1",
            },
            analysis_request={
                "task": "xxx_chain_bethe_integral",
                "quadrature_orders": [64, 128],
                "integration_cutoff": 40.0,
                "observable": "ground_state_energy_per_site",
                "units": "J",
            },
        ),
        LiteratureModelCase(
            case_id="two_dimensional_square_ising_onsager_tc",
            source_id="Onsager_1944",
            claim_id="critical_temperature",
            input_route="structured",
            model_input={
                "representation": "operator",
                "support": [0, 1],
                "expression": "-J*(4*Sz@0 Sz@1)",
                "parameters": {"J": 1.0},
                "local_dim": 2,
                "lattice": {
                    "kind": "square",
                    "dimension": 2,
                    "positions": [[0.0, 0.0, 0.0]],
                    "lattice_vectors": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                    "bond_orbits": [
                        {
                            "orbit_ref": "bond-orbit:1",
                            "kind": "pair",
                            "directed": False,
                            "orientation_convention": "undirected",
                            "source_labels": ["1"],
                            "shell": 1,
                            "representative": {
                                "source": 0,
                                "target": 0,
                                "translation": [1, 0, 0],
                            },
                            "members": [
                                {
                                    "source": 0,
                                    "target": 0,
                                    "translation": [1, 0, 0],
                                    "generated_by_operation_ref": "explicit",
                                },
                                {
                                    "source": 0,
                                    "target": 0,
                                    "translation": [0, 1, 0],
                                    "generated_by_operation_ref": "explicit",
                                },
                            ],
                            "reverse_orientation": {
                                "kind": "same_undirected_bond",
                                "source_target_swap": True,
                                "transpose": False,
                                "translation": [-1, 0, 0],
                            },
                            "selection_aliases": ["1"],
                        }
                    ],
                    "bond_orbit_shell_map": {
                        "1": {"shell_index": 1, "distance": 1.0},
                    },
                    "bond_orbit_representative_map": {
                        "1": {
                            "source": 0,
                            "target": 0,
                            "translation": [1, 0, 0],
                        },
                    },
                },
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "1",
            },
            analysis_request={
                "task": "scalar_root",
                "variable": "T",
                "equation": "sinh(2*J/T) - 1",
                "parameters": {"J": 1.0},
                "bracket": [0.1, 10.0],
                "absolute_tolerance": 1.0e-12,
                "observable": "critical_temperature",
                "units": "J/k_B",
            },
        ),
        _classical_ising_entropy_case(
            case_id="triangular_ising_antiferromagnet_residual_entropy",
            source_id="Wannier_1950",
            claim_id="triangular_residual_entropy_per_spin",
            lattice={
                "kind": "triangular",
                "dimension": 2,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.5, math.sqrt(3.0) / 2.0, 0.0],
                    [0.0, 0.0, 8.0],
                ],
                "representative": {
                    "source": 0,
                    "target": 0,
                    "translation": [1, 0, 0],
                },
                "members": [
                    {"source": 0, "target": 0, "translation": [1, 0, 0]},
                    {"source": 0, "target": 0, "translation": [0, 1, 0]},
                    {"source": 0, "target": 0, "translation": [1, -1, 0]},
                ],
            },
            supercells=[[2, 2], [3, 2], [4, 2]],
        ),
        _classical_ising_entropy_case(
            case_id=(
                "kagome_ising_antiferromagnet_residual_entropy_reference"
            ),
            source_id="Kano_Naya_1953",
            claim_id="kagome_residual_entropy_per_spin",
            lattice={
                "kind": "kagome",
                "dimension": 2,
                "positions": [
                    [0.0, 0.0, 0.0],
                    [0.5, 0.0, 0.0],
                    [0.0, 0.5, 0.0],
                ],
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.5, math.sqrt(3.0) / 2.0, 0.0],
                    [0.0, 0.0, 8.0],
                ],
                "representative": {
                    "source": 0,
                    "target": 1,
                    "translation": [0, 0, 0],
                },
                "members": [
                    {"source": 0, "target": 1, "translation": [0, 0, 0]},
                    {"source": 0, "target": 1, "translation": [-1, 0, 0]},
                    {"source": 0, "target": 2, "translation": [0, 0, 0]},
                    {"source": 0, "target": 2, "translation": [0, -1, 0]},
                    {"source": 1, "target": 2, "translation": [0, 0, 0]},
                    {"source": 1, "target": 2, "translation": [1, -1, 0]},
                ],
            },
            supercells=[[1, 1], [2, 1], [2, 2]],
        ),
        LiteratureModelCase(
            case_id="xy_spin_half_chain_anisotropic_critical_line",
            source_id="Barouch_McCoy_1971",
            claim_id="critical_line",
            input_route="structured",
            model_input={
                "representation": "operator",
                "support": [0, 1],
                "expression": (
                    "-Jx*Sx@0 Sx@1 - Jy*Sy@0 Sy@1"
                ),
                "parameters": {"Jx": 1.5, "Jy": 0.5},
                "local_dim": 2,
                "lattice": {
                    "kind": "chain",
                    "dimension": 1,
                    "positions": [[0.0, 0.0, 0.0]],
                    "lattice_vectors": [
                        [1.0, 0.0, 0.0],
                        [0.0, 8.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                    "bond_orbit_shell_map": {
                        "1": {"shell_index": 1, "distance": 1.0},
                    },
                    "bond_orbit_representative_map": {
                        "1": {
                            "source": 0,
                            "target": 0,
                            "translation": [1, 0, 0],
                        },
                    },
                },
                "onsite_terms": [
                    {
                        "kind": "linear_spin_cartesian",
                        "site_scope": {"kind": "site", "site": 0},
                        "operator_basis": {
                            "bond_label": "spin_cartesian",
                            "components": ["Sx", "Sy", "Sz"],
                        },
                        "frame": {
                            "kind": "global_cartesian",
                            "axes": ["x", "y", "z"],
                        },
                        "payload": {"vector": [0.0, 0.0, -0.25]},
                        "provenance": {
                            "source_kind": "answer_free_model_input"
                        },
                    }
                ],
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "1",
            },
            analysis_request={
                "task": "xy_chain_free_fermion_boundaries",
                "observable": "critical_boundaries",
                "units": "model_parameter_units",
            },
        ),
        LiteratureModelCase(
            case_id="transverse_field_ising_chain_critical_point",
            source_id="Dziarmaga_2005",
            claim_id="tfim_critical_field",
            input_route="structured",
            model_input={
                "representation": "operator",
                "support": [0, 1],
                "expression": "-J*(4*Sz@0 Sz@1)",
                "parameters": {"J": 1.0, "h": 0.6},
                "local_dim": 2,
                "lattice": {
                    "kind": "chain",
                    "dimension": 1,
                    "positions": [[0.0, 0.0, 0.0]],
                    "lattice_vectors": [
                        [1.0, 0.0, 0.0],
                        [0.0, 8.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                    "bond_orbit_shell_map": {
                        "1": {"shell_index": 1, "distance": 1.0},
                    },
                    "bond_orbit_representative_map": {
                        "1": {
                            "source": 0,
                            "target": 0,
                            "translation": [1, 0, 0],
                        },
                    },
                },
                "onsite_terms": [
                    {
                        "kind": "linear_spin_cartesian",
                        "site_scope": {"kind": "site", "site": 0},
                        "operator_basis": {
                            "bond_label": "spin_cartesian",
                            "components": ["Sx", "Sy", "Sz"],
                        },
                        "frame": {
                            "kind": "global_cartesian",
                            "axes": ["x", "y", "z"],
                        },
                        "payload": {"vector": [-1.2, 0.0, 0.0]},
                        "provenance": {
                            "source_kind": "answer_free_model_input"
                        },
                    }
                ],
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "1",
            },
            analysis_request={
                "task": "ising_chain_free_fermion",
                "observable": "critical_field",
                "momenta": [
                    0.0,
                    math.pi / 4.0,
                    math.pi / 2.0,
                    3.0 * math.pi / 4.0,
                    math.pi,
                ],
                "units": "J",
            },
        ),
        LiteratureModelCase(
            case_id="xx_spin_half_chain_free_fermion_energy",
            source_id="Lieb_Schultz_Mattis_1961",
            claim_id="xx_chain_ground_state_energy_per_site",
            input_route="structured",
            model_input={
                "representation": "operator",
                "support": [0, 1],
                "expression": "J*(Sx@0 Sx@1 + Sy@0 Sy@1)",
                "parameters": {"J": 1.0},
                "local_dim": 2,
                "lattice": {
                    "kind": "chain",
                    "dimension": 1,
                    "positions": [[0.0, 0.0, 0.0]],
                    "lattice_vectors": [
                        [1.0, 0.0, 0.0],
                        [0.0, 8.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                    "bond_orbit_shell_map": {
                        "1": {"shell_index": 1, "distance": 1.0},
                    },
                    "bond_orbit_representative_map": {
                        "1": {
                            "source": 0,
                            "target": 0,
                            "translation": [1, 0, 0],
                        },
                    },
                },
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "1",
            },
            analysis_request={
                "task": "xx_chain_free_fermion",
                "observable": "ground_state_energy_per_site",
                "grid_sizes": [8192, 16384],
                "units": "J",
            },
        ),
        _classical_ising_critical_case(
            case_id="triangular_ising_ferromagnet_exact_tc",
            source_id="Husimi_Syozi_1950",
            claim_id="triangular_critical_temperature",
            lattice={
                "kind": "triangular",
                "dimension": 2,
                "positions": [[0.0, 0.0, 0.0]],
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.5, math.sqrt(3.0) / 2.0, 0.0],
                    [0.0, 0.0, 8.0],
                ],
                "representative": {
                    "source": 0,
                    "target": 0,
                    "translation": [1, 0, 0],
                },
                "members": [
                    {"source": 0, "target": 0, "translation": [1, 0, 0]},
                    {"source": 0, "target": 0, "translation": [0, 1, 0]},
                    {"source": 0, "target": 0, "translation": [1, -1, 0]},
                ],
            },
            equation="exp(4*J/T) - 3",
        ),
        _classical_ising_critical_case(
            case_id="honeycomb_ising_ferromagnet_exact_tc",
            source_id="Husimi_Syozi_1950",
            claim_id="honeycomb_critical_temperature",
            lattice={
                "kind": "honeycomb",
                "dimension": 2,
                "positions": [
                    [0.0, 0.0, 0.0],
                    [1.0 / 3.0, 1.0 / 3.0, 0.0],
                ],
                "lattice_vectors": [
                    [math.sqrt(3.0) / 2.0, 1.5, 0.0],
                    [-math.sqrt(3.0) / 2.0, 1.5, 0.0],
                    [0.0, 0.0, 8.0],
                ],
                "representative": {
                    "source": 0,
                    "target": 1,
                    "translation": [0, 0, 0],
                },
                "members": [
                    {"source": 0, "target": 1, "translation": [0, 0, 0]},
                    {"source": 0, "target": 1, "translation": [-1, 0, 0]},
                    {"source": 0, "target": 1, "translation": [0, -1, 0]},
                ],
            },
            equation="exp(2*J/T) - (2 + sqrt(3))",
        ),
        _classical_ising_critical_case(
            case_id="kagome_ising_ferromagnet_exact_tc",
            source_id="Kano_Naya_1953",
            claim_id="kagome_critical_temperature",
            lattice={
                "kind": "kagome",
                "dimension": 2,
                "positions": [
                    [0.0, 0.0, 0.0],
                    [0.5, 0.0, 0.0],
                    [0.0, 0.5, 0.0],
                ],
                "lattice_vectors": [
                    [1.0, 0.0, 0.0],
                    [0.5, math.sqrt(3.0) / 2.0, 0.0],
                    [0.0, 0.0, 8.0],
                ],
                "representative": {
                    "source": 0,
                    "target": 1,
                    "translation": [0, 0, 0],
                },
                "members": [
                    {"source": 0, "target": 1, "translation": [0, 0, 0]},
                    {"source": 0, "target": 1, "translation": [-1, 0, 0]},
                    {"source": 0, "target": 2, "translation": [0, 0, 0]},
                    {"source": 0, "target": 2, "translation": [0, -1, 0]},
                    {"source": 1, "target": 2, "translation": [0, 0, 0]},
                    {"source": 1, "target": 2, "translation": [1, -1, 0]},
                ],
            },
            equation="exp(4*J/T) - (3 + 2*sqrt(3))",
        ),
        LiteratureModelCase(
            case_id="aklt_spin1_chain_projector_ground_state",
            source_id="Affleck_Kennedy_Lieb_Tasaki_1987",
            claim_id="aklt_two_site_projector_spectrum",
            input_route="matrix",
            model_input={
                "representation": "matrix",
                "support": [0, 1],
                "matrix": _spin_one_total_spin_two_projector(),
                "local_dim": 3,
                "local_hilbert": _spin_one_two_site_hilbert(),
                "lattice": {
                    "kind": "chain",
                    "dimension": 1,
                    "positions": [[0.0, 0.0, 0.0]],
                    "lattice_vectors": [
                        [1.0, 0.0, 0.0],
                        [0.0, 8.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                    "bond_orbit_shell_map": {
                        "1": {"shell_index": 1, "distance": 1.0},
                    },
                    "bond_orbit_representative_map": {
                        "1": {
                            "source": 0,
                            "target": 0,
                            "translation": [1, 0, 0],
                        },
                    },
                },
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "1",
            },
            analysis_request={
                "task": "local_spectrum",
                "observable": "eigenvalues",
                "units": "projector_energy",
            },
        ),
        LiteratureModelCase(
            case_id="majundar_ghosh_chain_exact_dimer_point",
            source_id="Caspers_Emmett_Magnus_1984",
            claim_id="majumdar_ghosh_ground_state_summary",
            input_route="structured",
            model_input={
                "representation": "operator_channel_collection",
                "support": [0, 1],
                "expressions": [
                    {
                        "block_kind": "J1",
                        "expression": (
                            "J1*(Sx@0 Sx@1 + Sy@0 Sy@1 + Sz@0 Sz@1)"
                        ),
                    },
                    {
                        "block_kind": "J2",
                        "expression": (
                            "J2*(Sx@0 Sx@1 + Sy@0 Sy@1 + Sz@0 Sz@1)"
                        ),
                    },
                ],
                "parameters": {"J1": 1.0, "J2": 0.5},
                "local_dim": 2,
                "lattice": {
                    "kind": "chain",
                    "dimension": 1,
                    "positions": [[0.0, 0.0, 0.0]],
                    "lattice_vectors": [
                        [1.0, 0.0, 0.0],
                        [0.0, 8.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                    "bond_orbits": [
                        {
                            "orbit_ref": f"bond-orbit:{term_kind}",
                            "kind": "pair",
                            "directed": False,
                            "orientation_convention": "undirected",
                            "source_labels": [term_kind],
                            "shell": distance,
                            "representative": {
                                "source": 0,
                                "target": 0,
                                "translation": [distance, 0, 0],
                            },
                            "members": [
                                {
                                    "source": 0,
                                    "target": 0,
                                    "translation": [distance, 0, 0],
                                    "generated_by_operation_ref": "explicit",
                                }
                            ],
                            "reverse_orientation": {
                                "kind": "same_undirected_bond",
                                "source_target_swap": True,
                                "transpose": False,
                                "translation": [-distance, 0, 0],
                            },
                            "selection_aliases": [term_kind],
                        }
                        for term_kind, distance in (("J1", 1), ("J2", 2))
                    ],
                },
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "J1",
            },
            analysis_request={
                "task": "finite_cluster_ed",
                "term_orbit_map": {
                    "J1": "bond-orbit:J1",
                    "J2": "bond-orbit:J2",
                },
                "supercell": [4],
                "observable": "ground_state_summary",
                "units": "J1",
            },
        ),
        LiteratureModelCase(
            case_id="square_compass_model_directional_exchange_degeneracy",
            source_id="Nussinov_van_den_Brink_2015",
            claim_id="square_compass_line_flip_symmetries",
            input_route="structured",
            model_input={
                "representation": "operator_channel_collection",
                "support": [0, 1],
                "expressions": [
                    {
                        "block_kind": "horizontal",
                        "expression": "Jx*Sx@0 Sx@1",
                    },
                    {
                        "block_kind": "vertical",
                        "expression": "Jz*Sz@0 Sz@1",
                    },
                ],
                "parameters": {"Jx": 1.0, "Jz": 1.0},
                "local_dim": 2,
                "lattice": {
                    "kind": "square",
                    "dimension": 2,
                    "positions": [[0.0, 0.0, 0.0]],
                    "lattice_vectors": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                    "bond_orbits": [
                        {
                            "orbit_ref": f"bond-orbit:{term_kind}",
                            "kind": "pair",
                            "directed": False,
                            "orientation_convention": "undirected",
                            "source_labels": [term_kind],
                            "shell": 1,
                            "representative": {
                                "source": 0,
                                "target": 0,
                                "translation": translation,
                            },
                            "members": [
                                {
                                    "source": 0,
                                    "target": 0,
                                    "translation": translation,
                                    "generated_by_operation_ref": "explicit",
                                }
                            ],
                            "reverse_orientation": {
                                "kind": "same_undirected_bond",
                                "source_target_swap": True,
                                "transpose": False,
                                "translation": [
                                    -component for component in translation
                                ],
                            },
                            "selection_aliases": [term_kind],
                        }
                        for term_kind, translation in (
                            ("horizontal", [1, 0, 0]),
                            ("vertical", [0, 1, 0]),
                        )
                    ],
                },
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "horizontal",
            },
            analysis_request={
                "task": "finite_cluster_ed",
                "term_orbit_map": {
                    "horizontal": "bond-orbit:horizontal",
                    "vertical": "bond-orbit:vertical",
                },
                "supercell": [2, 2],
                "observable": "all_operator_products_commute",
                "commuting_operator_products": [
                    {"operator": "Sz", "sites": [0, 2]},
                    {"operator": "Sz", "sites": [1, 3]},
                    {"operator": "Sx", "sites": [0, 1]},
                    {"operator": "Sx", "sites": [2, 3]},
                ],
                "units": "dimensionless",
            },
        ),
        LiteratureModelCase(
            case_id="two_leg_ladder_strong_rung_exact_limit",
            source_id="Dagotto_Rice_1996",
            claim_id="strong_rung_spectral_gap",
            input_route="structured",
            model_input={
                "representation": "operator",
                "support": [0, 1],
                "expression": (
                    "J_rung*(Sx@0 Sx@1 + Sy@0 Sy@1 + Sz@0 Sz@1)"
                ),
                "parameters": {"J_rung": 1.0},
                "local_dim": 2,
                "lattice": {
                    "kind": "two_leg_ladder",
                    "dimension": 1,
                    "positions": [
                        [0.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                    ],
                    "lattice_vectors": [
                        [1.0, 0.0, 0.0],
                        [0.0, 8.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                    "bond_orbits": [
                        {
                            "orbit_ref": "bond-orbit:rung",
                            "kind": "pair",
                            "directed": False,
                            "orientation_convention": "undirected",
                            "source_labels": ["rung"],
                            "shell": 1,
                            "representative": {
                                "source": 0,
                                "target": 1,
                                "translation": [0, 0, 0],
                            },
                            "members": [
                                {
                                    "source": 0,
                                    "target": 1,
                                    "translation": [0, 0, 0],
                                    "generated_by_operation_ref": "explicit",
                                }
                            ],
                            "reverse_orientation": {
                                "kind": "same_undirected_bond",
                                "source_target_swap": True,
                                "transpose": False,
                                "translation": [0, 0, 0],
                            },
                            "selection_aliases": ["rung"],
                        }
                    ],
                },
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "rung",
            },
            analysis_request={
                "task": "local_spectrum",
                "observable": "spectral_gap",
                "units": "J_rung",
            },
        ),
        LiteratureModelCase(
            case_id="shastry_sutherland_exact_dimer_product",
            source_id="Shastry_Sutherland_1981",
            claim_id="shastry_sutherland_dimer_energy",
            input_route="structured",
            model_input={
                "representation": "operator",
                "support": [0, 1],
                "expression": (
                    "J_dimer*(Sx@0 Sx@1 + Sy@0 Sy@1 + Sz@0 Sz@1)"
                ),
                "parameters": {"J_dimer": 1.0},
                "local_dim": 2,
                "lattice": {
                    "kind": "shastry_sutherland",
                    "dimension": 2,
                    "positions": [
                        [0.0, 0.0, 0.0],
                        [0.5, 0.5, 0.0],
                    ],
                    "lattice_vectors": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                    "bond_orbits": [
                        {
                            "orbit_ref": "bond-orbit:dimer",
                            "kind": "pair",
                            "directed": False,
                            "orientation_convention": "undirected",
                            "source_labels": ["dimer"],
                            "shell": 1,
                            "representative": {
                                "source": 0,
                                "target": 1,
                                "translation": [0, 0, 0],
                            },
                            "members": [
                                {
                                    "source": 0,
                                    "target": 1,
                                    "translation": [0, 0, 0],
                                    "generated_by_operation_ref": "explicit",
                                }
                            ],
                            "reverse_orientation": {
                                "kind": "same_undirected_bond",
                                "source_target_swap": True,
                                "transpose": False,
                                "translation": [0, 0, 0],
                            },
                            "selection_aliases": ["dimer"],
                        }
                    ],
                },
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "dimer",
            },
            analysis_request={
                "task": "local_spectrum",
                "observable": "ground_state_energy",
                "units": "J_dimer",
            },
        ),
        LiteratureModelCase(
            case_id="spin_ice_tetrahedron_nn_ice_rule",
            source_id="Harris_et_al_1997",
            claim_id="tetrahedron_energy_levels",
            input_route="structured",
            model_input={
                "representation": "operator",
                "support": [0, 1, 2, 3],
                "expression": (
                    "J*(4*Sz@0 Sz@1 + 4*Sz@0 Sz@2 + "
                    "4*Sz@0 Sz@3 + 4*Sz@1 Sz@2 + "
                    "4*Sz@1 Sz@3 + 4*Sz@2 Sz@3)"
                ),
                "parameters": {"J": 1.0},
                "local_dim": 2,
                "lattice": {
                    "kind": "tetrahedron",
                    "dimension": 0,
                    "positions": [
                        [0.0, 0.0, 0.0],
                        [0.0, 0.5, 0.5],
                        [0.5, 0.0, 0.5],
                        [0.5, 0.5, 0.0],
                    ],
                    "lattice_vectors": [
                        [8.0, 0.0, 0.0],
                        [0.0, 8.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                    "bond_orbits": [
                        {
                            "orbit_ref": "bond-orbit:tetrahedron",
                            "kind": "pair",
                            "directed": False,
                            "orientation_convention": "undirected",
                            "source_labels": ["tetrahedron"],
                            "shell": 1,
                            "representative": {
                                "source": 0,
                                "target": 1,
                                "translation": [0, 0, 0],
                            },
                            "members": [
                                {
                                    "source": left,
                                    "target": right,
                                    "translation": [0, 0, 0],
                                    "generated_by_operation_ref": "explicit",
                                }
                                for left, right in (
                                    (0, 1),
                                    (0, 2),
                                    (0, 3),
                                    (1, 2),
                                    (1, 3),
                                    (2, 3),
                                )
                            ],
                            "reverse_orientation": {
                                "kind": "same_undirected_bond",
                                "source_target_swap": True,
                                "transpose": False,
                                "translation": [0, 0, 0],
                            },
                            "selection_aliases": ["tetrahedron"],
                        }
                    ],
                },
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "tetrahedron",
            },
            analysis_request={
                "task": "classical_sz_enumeration",
                "observable": "tetrahedron_energy_levels",
                "units": "J",
            },
        ),
        LiteratureModelCase(
            case_id=(
                "checkerboard_heisenberg_afm_planar_pyrochlore_reference"
            ),
            source_id="Fouet_et_al_arXiv_cond-mat_0108070",
            claim_id="crossed_plaquette_zero_total_spin",
            input_route="structured",
            model_input={
                "representation": "operator",
                "support": [0, 1],
                "expression": (
                    "J*(Sx@0 Sx@1 + Sy@0 Sy@1 + Sz@0 Sz@1)"
                ),
                "parameters": {"J": 1.0},
                "local_dim": 2,
                "lattice": {
                    "kind": "checkerboard_crossed_plaquette",
                    "dimension": 0,
                    "positions": [
                        [0.0, 0.0, 0.0],
                        [1.0, 0.0, 0.0],
                        [1.0, 1.0, 0.0],
                        [0.0, 1.0, 0.0],
                    ],
                    "lattice_vectors": [
                        [8.0, 0.0, 0.0],
                        [0.0, 8.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                    "bond_orbits": [
                        {
                            "orbit_ref": "bond-orbit:crossed-plaquette",
                            "kind": "pair",
                            "directed": False,
                            "orientation_convention": "undirected",
                            "source_labels": ["crossed-plaquette"],
                            "shell": 1,
                            "representative": {
                                "source": 0,
                                "target": 1,
                                "translation": [0, 0, 0],
                            },
                            "members": [
                                {
                                    "source": left,
                                    "target": right,
                                    "translation": [0, 0, 0],
                                    "generated_by_operation_ref": "explicit",
                                }
                                for left, right in (
                                    (0, 1),
                                    (0, 2),
                                    (0, 3),
                                    (1, 2),
                                    (1, 3),
                                    (2, 3),
                                )
                            ],
                            "reverse_orientation": {
                                "kind": "same_undirected_bond",
                                "source_target_swap": True,
                                "transpose": False,
                                "translation": [0, 0, 0],
                            },
                            "selection_aliases": ["crossed-plaquette"],
                        }
                    ],
                },
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "crossed-plaquette",
            },
            analysis_request={
                "task": "finite_cluster_ed",
                "bond_orbit_ref": "bond-orbit:crossed-plaquette",
                "supercell": [],
                "observable": "zero_total_spin_ground_space",
                "units": "dimensionless",
            },
        ),
        LiteratureModelCase(
            case_id=(
                "one_dimensional_classical_ising_no_finite_t_transition"
            ),
            source_id="Ising_1925",
            claim_id="zero_temperature_limit",
            input_route="structured",
            model_input={
                "representation": "operator",
                "support": [0, 1],
                "expression": "-J1*(4*Sz@0 Sz@1)",
                "parameters": {"J1": 1.0},
                "lattice": {
                    "kind": "chain",
                    "dimension": 1,
                    "positions": [[0.0, 0.0, 0.0]],
                    "lattice_vectors": [
                        [1.0, 0.0, 0.0],
                        [0.0, 8.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                    "bond_orbit_shell_map": {
                        "1": {"shell_index": 1, "distance": 1.0},
                    },
                    "bond_orbit_representative_map": {
                        "1": {
                            "source": 0,
                            "target": 0,
                            "translation": [1, 0, 0],
                        },
                    },
                },
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "1",
            },
            analysis_request={
                "task": "one_dimensional_transfer_matrix",
                "diagnostic_temperatures": [0.5, 1.0, 2.0],
                "observable": "critical_temperature",
                "units": "J/k_B",
            },
        ),
        LiteratureModelCase(
            case_id="single_ion_spin1_anisotropy_levels",
            source_id="Blume_1966",
            claim_id="single_ion_levels",
            input_route="matrix",
            model_input={
                "representation": "matrix",
                "support": [0],
                "matrix": [[1, 0, 0], [0, 0, 0], [0, 0, 1]],
                "local_dim": 3,
                "lattice": {
                    "kind": "single_site",
                    "dimension": 0,
                    "positions": [[0.0, 0.0, 0.0]],
                },
                "classical_bond_label": "spin-only",
            },
            analysis_request={
                "task": "local_spectrum",
                "observable": "eigenvalues",
                "units": "D",
            },
        ),
        LiteratureModelCase(
            case_id=(
                "blume_capel_spin1_zero_temperature_level_crossing"
            ),
            source_id="Blume_1966",
            claim_id="blume_capel_zero_temperature_crossing",
            input_route="structured",
            model_input={
                "representation": "operator",
                "support": [0, 1],
                "expression": "-J*Sz@0 Sz@1",
                "parameters": {"J": 1.0, "D": 1.0},
                "local_dim": 3,
                "local_hilbert": {
                    "sites": [
                        {
                            "site_ref": "site:0",
                            "space_ref": "space:spin_s_1",
                            "basis_ref": "basis:spin_s_1",
                            "classical_space_ref": (
                                "classical_space:spin_unit_vector"
                            ),
                            "operator_basis_refs": [
                                "op_basis:spin_cartesian"
                            ],
                        },
                        {
                            "site_ref": "site:1",
                            "space_ref": "space:spin_s_1",
                            "basis_ref": "basis:spin_s_1",
                            "classical_space_ref": (
                                "classical_space:spin_unit_vector"
                            ),
                            "operator_basis_refs": [
                                "op_basis:spin_cartesian"
                            ],
                        },
                    ],
                    "basis_registry": {
                        "basis:spin_s_1": {
                            "kind": "spin_multiplet",
                            "dimension": 3,
                            "basis_order": ["m=1", "m=0", "m=-1"],
                        }
                    },
                    "operator_bases": {
                        "op_basis:spin_cartesian": {
                            "kind": "spin_cartesian",
                            "basis_order": ["Sx", "Sy", "Sz"],
                        }
                    },
                    "classical_spaces": {
                        "classical_space:spin_unit_vector": {
                            "kind": "unit_vector_sphere",
                            "dimension": 3,
                        }
                    },
                },
                "lattice": {
                    "kind": "square",
                    "dimension": 2,
                    "positions": [[0.0, 0.0, 0.0]],
                    "lattice_vectors": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 8.0],
                    ],
                    "bond_orbits": [
                        {
                            "orbit_ref": "bond-orbit:1",
                            "kind": "pair",
                            "directed": False,
                            "orientation_convention": "undirected",
                            "source_labels": ["1"],
                            "shell": 1,
                            "representative": {
                                "source": 0,
                                "target": 0,
                                "translation": [1, 0, 0],
                            },
                            "members": [
                                {
                                    "source": 0,
                                    "target": 0,
                                    "translation": [1, 0, 0],
                                    "generated_by_operation_ref": "explicit",
                                },
                                {
                                    "source": 0,
                                    "target": 0,
                                    "translation": [0, 1, 0],
                                    "generated_by_operation_ref": "explicit",
                                },
                            ],
                            "reverse_orientation": {
                                "kind": "same_undirected_bond",
                                "source_target_swap": True,
                                "transpose": False,
                                "translation": [-1, 0, 0],
                            },
                            "selection_aliases": ["1"],
                        }
                    ],
                },
                "onsite_terms": [
                    {
                        "kind": "quadratic_spin_cartesian",
                        "site_scope": {"kind": "site", "site": 0},
                        "operator_basis": {
                            "bond_label": "spin_cartesian",
                            "components": ["Sx", "Sy", "Sz"],
                        },
                        "frame": {
                            "kind": "global_cartesian",
                            "axes": ["x", "y", "z"],
                        },
                        "payload": {
                            "matrix": [
                                [0.0, 0.0, 0.0],
                                [0.0, 0.0, 0.0],
                                [0.0, 0.0, 1.0],
                            ]
                        },
                        "provenance": {
                            "source_kind": "answer_free_model_input"
                        },
                    }
                ],
                "classical_bond_label": "spin-only",
                "selected_local_bond_bond_label": "1",
            },
            analysis_request={
                "task": "scalar_root",
                "variable": "D",
                "equation": "D - z*J/2",
                "parameters": {"z": 4.0, "J": 1.0},
                "bracket": [0.0, 4.0],
                "absolute_tolerance": 1.0e-12,
                "observable": "zero_temperature_level_crossing",
                "units": "J",
            },
        ),
        _spin_one_chain_matrix_case(
            case_id="bilinear_biquadratic_spin1_chain_aklt_angle",
            source_id="Affleck_Kennedy_Lieb_Tasaki_1987",
            claim_id="aklt_bilinear_biquadratic_coefficients",
            matrix=_spin_one_total_spin_two_projector(),
        ),
        _spin_one_chain_matrix_case(
            case_id="uimin_lai_sutherland_spin1_su3_point",
            source_id="Uimin_Lai_Sutherland",
            claim_id="uls_bilinear_biquadratic_coefficients",
            matrix=_spin_one_bilinear_biquadratic_matrix(1.0, 1.0),
        ),
        _pyrochlore_pauling_case(),
        _pyrochlore_heisenberg_case(),
        _simple_cubic_j1_j2_case(),
        _diamond_j1_j2_case(),
        _kitaev_field_case(),
        _toric_code_case(),
        _fully_frustrated_square_ising_case(),
    )


def initial_literature_claims():
    """Return paper-side values kept separate from product computation."""

    return (
        LiteratureClaim(
            claim_id="thermodynamic_limit_ground_state_energy",
            observable="ground_state_energy_per_site",
            value=0.25 - math.log(2.0),
            uncertainty=1.0e-10,
            units="J",
            source_location="Bethe 1931 isotropic spin-half chain",
        ),
        LiteratureClaim(
            claim_id="critical_temperature",
            observable="critical_temperature",
            value=2.269185314213022,
            uncertainty=1.0e-10,
            units="J/k_B",
            source_location="Phys. Rev. 65, 117 (1944)",
        ),
        LiteratureClaim(
            claim_id="single_ion_levels",
            observable="eigenvalues",
            value=[0.0, 1.0, 1.0],
            uncertainty=1.0e-12,
            units="D",
            source_location="Blume 1966 single-ion level structure",
        ),
        LiteratureClaim(
            claim_id="zero_temperature_limit",
            observable="critical_temperature",
            value=0.0,
            uncertainty=0.0,
            units="J/k_B",
            source_location="Ising 1925 one-dimensional chain",
        ),
        LiteratureClaim(
            claim_id="tfim_critical_field",
            observable="critical_field",
            value=1.0,
            uncertainty=1.0e-12,
            units="J",
            source_location="Dziarmaga 2005 transverse-field Ising chain",
        ),
        LiteratureClaim(
            claim_id="critical_line",
            observable="critical_boundaries",
            value={
                "ising_critical_field": 1.0,
                "anisotropy_transition_gamma": 0.0,
            },
            uncertainty=1.0e-12,
            units="model_parameter_units",
            source_location="Barouch and McCoy 1971 XY-chain boundaries",
        ),
        LiteratureClaim(
            claim_id="xx_chain_ground_state_energy_per_site",
            observable="ground_state_energy_per_site",
            value=-1.0 / math.pi,
            uncertainty=1.0e-8,
            units="J",
            source_location=(
                "Lieb, Schultz, and Mattis 1961 spin-half XX chain"
            ),
        ),
        LiteratureClaim(
            claim_id="triangular_critical_temperature",
            observable="critical_temperature",
            value=4.0 / math.log(3.0),
            uncertainty=1.0e-10,
            units="J/k_B",
            source_location="Husimi and Syozi 1950 triangular lattice",
        ),
        LiteratureClaim(
            claim_id="honeycomb_critical_temperature",
            observable="critical_temperature",
            value=2.0 / math.log(2.0 + math.sqrt(3.0)),
            uncertainty=1.0e-10,
            units="J/k_B",
            source_location="Husimi and Syozi 1950 honeycomb lattice",
        ),
        LiteratureClaim(
            claim_id="kagome_critical_temperature",
            observable="critical_temperature",
            value=4.0 / math.log(3.0 + 2.0 * math.sqrt(3.0)),
            uncertainty=1.0e-10,
            units="J/k_B",
            source_location="Kano and Naya 1953 kagome lattice",
        ),
        LiteratureClaim(
            claim_id="tetrahedron_energy_levels",
            observable="tetrahedron_energy_levels",
            value=[
                {"energy": -2.0, "degeneracy": 6},
                {"energy": 0.0, "degeneracy": 8},
                {"energy": 6.0, "degeneracy": 2},
            ],
            uncertainty=0.0,
            units="J",
            source_location="Harris et al. 1997 tetrahedron ice rule",
        ),
        LiteratureClaim(
            claim_id="crossed_plaquette_zero_total_spin",
            observable="zero_total_spin_ground_space",
            value=True,
            uncertainty=0.0,
            units="dimensionless",
            source_location="Fouet et al. crossed-plaquette constraint",
        ),
        LiteratureClaim(
            claim_id="strong_rung_spectral_gap",
            observable="spectral_gap",
            value=1.0,
            uncertainty=1.0e-12,
            units="J_rung",
            source_location="Dagotto and Rice 1996 strong-rung limit",
        ),
        LiteratureClaim(
            claim_id="aklt_two_site_projector_spectrum",
            observable="eigenvalues",
            value=[0.0] * 4 + [1.0] * 5,
            uncertainty=1.0e-12,
            units="projector_energy",
            source_location="Affleck et al. 1987 two-site AKLT projector",
        ),
        LiteratureClaim(
            claim_id="majumdar_ghosh_ground_state_summary",
            observable="ground_state_summary",
            value={
                "energy_per_site": -0.375,
                "ground_state_degeneracy": 2,
            },
            uncertainty=1.0e-10,
            units="J1",
            source_location="Caspers et al. 1984 Majumdar-Ghosh point",
        ),
        LiteratureClaim(
            claim_id="square_compass_line_flip_symmetries",
            observable="all_operator_products_commute",
            value=True,
            uncertainty=0.0,
            units="dimensionless",
            source_location="Nussinov and van den Brink 2015 line symmetries",
        ),
        LiteratureClaim(
            claim_id="shastry_sutherland_dimer_energy",
            observable="ground_state_energy",
            value=-0.75,
            uncertainty=1.0e-12,
            units="J_dimer",
            source_location="Shastry and Sutherland 1981 dimer limit",
        ),
        LiteratureClaim(
            claim_id="blume_capel_zero_temperature_crossing",
            observable="zero_temperature_level_crossing",
            value=2.0,
            uncertainty=1.0e-10,
            units="J",
            source_location=(
                "Blume 1966 square-lattice zero-temperature boundary"
            ),
        ),
        LiteratureClaim(
            claim_id="aklt_bilinear_biquadratic_coefficients",
            observable="coefficient_summary",
            value={
                "bilinear_biquadratic_ratio": 1.0 / 3.0,
                "theta_radians": math.atan(1.0 / 3.0),
                "su3_symmetric": False,
            },
            uncertainty=1.0e-10,
            units="dimensionless",
            source_location="Affleck et al. 1987 spin-two projector",
        ),
        LiteratureClaim(
            claim_id="uls_bilinear_biquadratic_coefficients",
            observable="coefficient_summary",
            value={
                "bilinear_biquadratic_ratio": 1.0,
                "theta_radians": math.pi / 4.0,
                "su3_symmetric": True,
            },
            uncertainty=1.0e-10,
            units="dimensionless",
            source_location="Uimin, Lai, and Sutherland integrable point",
        ),
        LiteratureClaim(
            claim_id="pyrochlore_pauling_entropy_per_spin",
            observable="pauling_entropy_per_spin",
            value=0.5 * math.log(1.5),
            uncertainty=1.0e-12,
            units="k_B/spin",
            source_location="Pauling approximation for pyrochlore spin ice",
        ),
        LiteratureClaim(
            claim_id="pyrochlore_coulomb_constraint",
            observable="flat_band_constraint_summary",
            value={
                "zero_total_spin_per_tetrahedron": True,
                "pinch_points": True,
            },
            uncertainty=0.0,
            units="dimensionless",
            source_location="Moessner and Chalker 1998 pyrochlore constraint",
        ),
        LiteratureClaim(
            claim_id="simple_cubic_neel_collinear_boundary",
            observable="neel_to_collinear_boundary_j2_over_j1",
            value=0.25,
            uncertainty=1.0e-12,
            units="J2/J1",
            source_location="Pinettes and Diep simple-cubic J1-J2 boundary",
        ),
        LiteratureClaim(
            claim_id="diamond_spiral_surface_threshold",
            observable="spiral_surface_for_j2_over_j1_gt",
            value=0.125,
            uncertainty=1.0e-6,
            units="J2/J1",
            source_location="Bergman et al. 2007 diamond-lattice spiral onset",
        ),
        LiteratureClaim(
            claim_id="kitaev_field_opens_non_abelian_gap",
            observable="field_opens_non_abelian_gap",
            value=True,
            uncertainty=0.0,
            units="dimensionless",
            source_location="Kitaev 2006 weak-field Majorana mass",
        ),
        LiteratureClaim(
            claim_id="toric_code_torus_ground_state_degeneracy",
            observable="torus_ground_state_degeneracy",
            value=4,
            uncertainty=0.0,
            units="states",
            source_location="Kitaev 2003 toric-code stabilizer rank",
        ),
        LiteratureClaim(
            claim_id="fully_frustrated_macroscopic_degeneracy",
            observable="macroscopic_ground_state_degeneracy",
            value=True,
            uncertainty=0.0,
            units="dimensionless",
            source_location="Villain 1977 fully frustrated square Ising model",
        ),
    )


def write_eligible_workflow_report(
    csv_path, markdown_path, *, cases, claims=()
):
    """Write current layered coverage derived from fresh workflow runs."""

    rows = build_eligible_workflow_inventory(cases, claims=claims)
    summary = {
        "eligible_models": len(rows),
        "migrated_models": sum(
            row["migration_status"] == "migrated" for row in rows
        ),
        "not_migrated_models": sum(
            row["migration_status"] == "not_migrated" for row in rows
        ),
        "normalized_models": sum(
            row["normalization_status"] == "completed" for row in rows
        ),
        "simplified_models": sum(
            row["simplification_status"] == "completed" for row in rows
        ),
        "analyzed_models": sum(
            row["analysis_status"] == "completed" for row in rows
        ),
        "convergence_satisfied_models": sum(
            row["convergence_status"] == "satisfied" for row in rows
        ),
        "convergence_not_applicable_models": sum(
            row["convergence_status"] == "not_applicable" for row in rows
        ),
        "inconclusive_models": sum(
            row["analysis_status"] == "inconclusive" for row in rows
        ),
        "oracle_verified_models": sum(
            row["oracle_status"] == "verified" for row in rows
        ),
        "literature_matched_models": sum(
            row["literature_match_status"] == "matched" for row in rows
        ),
    }

    csv_path = Path(csv_path)
    markdown_path = Path(markdown_path)
    field_names = tuple(rows[0]) if rows else ()
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(rows)

    labels = (
        ("Eligible models", "eligible_models"),
        ("Migrated to generic workflow", "migrated_models"),
        ("Not migrated", "not_migrated_models"),
        ("Normalized", "normalized_models"),
        ("Simplified", "simplified_models"),
        ("Analyzed by a generic backend", "analyzed_models"),
        ("Convergence satisfied", "convergence_satisfied_models"),
        (
            "Convergence not applicable to exact finite/algebraic result",
            "convergence_not_applicable_models",
        ),
        ("Inconclusive", "inconclusive_models"),
        ("Independent oracle verified", "oracle_verified_models"),
        (
            "Matched to literature after computation",
            "literature_matched_models",
        ),
    )
    lines = [
        "# Literature Models Through the Generic Workflow",
        "",
        "This report is generated from fresh generic-workflow runs. Paper "
        "claims and oracle results are not inputs to model computation.",
        "",
        "| Layer | Count |",
        "|---|---:|",
    ]
    lines.extend(
        f"| {label} | {summary[key]} |" for label, key in labels
    )
    lines.extend(
        [
            "",
            "## Model status",
            "",
            "| Model | Backend family | Migration | Normalize | Simplify | Backend | Computation | Convergence | Oracle | Literature match | Blocker |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            "| {model_id} | {adapter_backend_kind} | {migration_status} | "
            "{normalization_status} | {simplification_status} | "
            "{backend_status} | {computation_status} | "
            "{convergence_status} | {oracle_status} | "
            "{literature_match_status} | "
            "{blocker} |".format(
                **{
                    **row,
                    "blocker": row["blocker"] or "",
                }
            )
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def write_registered_workflow_report(
    csv_path,
    markdown_path,
    *,
    registry_entries=None,
    cases=(),
    claims=(),
):
    """Write the honest layered status of all 155 registered claims."""

    rows = build_registered_workflow_inventory(
        registry_entries=registry_entries,
        cases=cases,
        claims=claims,
    )
    summary = {
        "registered_claims": len(rows),
        "canonical_sources": len(
            {row["canonical_source_identity"] for row in rows}
        ),
        "registered_models": len({row["model"] for row in rows}),
        "answer_free_models_landed": sum(
            row["migration_status"] == "migrated" for row in rows
        ),
        "answer_free_models_not_landed": sum(
            row["migration_status"] == "not_landed" for row in rows
        ),
        "claims_extracted_for_comparison": sum(
            row["claim_extraction_status"] == "extracted" for row in rows
        ),
        "normalized": sum(
            row["normalization_status"] == "completed" for row in rows
        ),
        "simplified": sum(
            row["simplification_status"] == "completed" for row in rows
        ),
        "computed": sum(
            row["analysis_status"] == "completed" for row in rows
        ),
        "convergence_satisfied": sum(
            row["convergence_status"] == "satisfied" for row in rows
        ),
        "convergence_not_applicable": sum(
            row["convergence_status"] == "not_applicable" for row in rows
        ),
        "inconclusive": sum(
            row["analysis_status"] == "inconclusive" for row in rows
        ),
        "oracle_verified": sum(
            row["oracle_status"] == "verified" for row in rows
        ),
        "literature_matched": sum(
            row["literature_match_status"] == "matched" for row in rows
        ),
        "unsupported": sum(
            row["analysis_status"] == "unsupported" for row in rows
        ),
        "needs_review": sum(
            row["migration_status"] == "not_landed" for row in rows
        ),
    }
    backend_gaps = Counter(
        row["registry_backend_needed"]
        for row in rows
        if row["migration_status"] == "not_landed"
    )

    csv_path = Path(csv_path)
    markdown_path = Path(markdown_path)
    field_names = tuple(rows[0]) if rows else ()
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(rows)

    labels = (
        ("Registered claims", "registered_claims"),
        ("Canonical literature sources", "canonical_sources"),
        ("Distinct registered models", "registered_models"),
        ("Answer-free model inputs landed", "answer_free_models_landed"),
        (
            "Answer-free model inputs not landed",
            "answer_free_models_not_landed",
        ),
        (
            "Claims extracted for post-computation comparison",
            "claims_extracted_for_comparison",
        ),
        ("Normalized", "normalized"),
        ("Simplified", "simplified"),
        ("Computed", "computed"),
        ("Convergence satisfied", "convergence_satisfied"),
        (
            "Convergence not applicable to exact finite/algebraic result",
            "convergence_not_applicable",
        ),
        ("Inconclusive", "inconclusive"),
        ("Independent oracle verified", "oracle_verified"),
        ("Matched to literature", "literature_matched"),
        ("Explicitly unsupported after model landing", "unsupported"),
        ("Needs model landing/review", "needs_review"),
    )
    lines = [
        "# Complete Literature-to-Generic-Workflow Inventory",
        "",
        "Paper-side target values are never computation inputs. The registry "
        "is used here only for source identity, model/observable metadata, and "
        "backend-gap classification. A row is counted as computed only when an "
        "answer-free model case runs through the generic product workflow.",
        "",
        "| Layer | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| {label} | {summary[key]} |" for label, key in labels)
    lines.extend(
        [
            "",
            "## Remaining reusable backend gaps",
            "",
            "| Registry backend family | Not-landed claims |",
            "|---|---:|",
        ]
    )
    for backend, count in sorted(
        backend_gaps.items(), key=lambda item: (-item[1], item[0])
    ):
        lines.append(f"| {backend} | {count} |")
    lines.extend(
        [
            "",
            "## Claim status",
            "",
            "| Claim | Canonical source | Model | Observable | Required backend | Model input | Normalize | Simplify | Analysis | Convergence | Oracle | Literature match | Blocker |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        values = (
            row["benchmark_name"],
            row["canonical_source_identity"],
            row["model"],
            row["observable"],
            row["registry_backend_needed"],
            row["model_input_status"],
            row["normalization_status"],
            row["simplification_status"],
            row["analysis_status"],
            row["convergence_status"],
            row["oracle_status"],
            row["literature_match_status"],
            row["blocker"] or "",
        )
        cells = [str(value).replace("|", "\\|") for value in values]
        lines.append("| " + " | ".join(cells) + " |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
