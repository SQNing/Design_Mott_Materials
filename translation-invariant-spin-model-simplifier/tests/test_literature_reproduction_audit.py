import ast
import sys
from collections.abc import Mapping
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from validation import literature_spin_model_benchmarks
from validation.literature_reproduction_audit import (
    build_literature_reproduction_audit as _build_literature_reproduction_audit,
    write_audit_markdown,
    write_remaining_strict_reproduction_gaps_markdown,
)


TEST_WEAK_EVIDENCE_MARKERS = (
    "candidate",
    "checked only",
    "material context",
    "not recomputed",
    " label",
)


def build_literature_reproduction_audit(**kwargs):
    """Keep metadata/report unit tests independent of the local source cache."""

    kwargs.setdefault("runtime_evidence_enabled", False)
    return _build_literature_reproduction_audit(**kwargs)


def _runtime_evidence_gaps(row, *, required_trace):
    gaps = []
    expected_mode = {
        "execution_trace": "local_recompute",
        "extraction_trace": "local_source_parse",
    }[required_trace]
    runtime_record = row.get("runtime_evidence_record") or row.get("evidence_record")
    if not isinstance(runtime_record, Mapping):
        gaps.append("mapping-like runtime evidence record")
    elif runtime_record.get("benchmark_name") != row["name"]:
        gaps.append("runtime evidence record benchmark identity")
    else:
        if runtime_record.get("evidence_mode") != expected_mode:
            gaps.append(f"runtime evidence record mode {expected_mode!r}")
        if not runtime_record.get("source_sha256"):
            gaps.append("nonempty source hash")
        if runtime_record.get("comparison", {}).get("matched") is not True:
            gaps.append("matched runtime comparison")
        if runtime_record.get("source_operand") != runtime_record.get(
            "registry_operand"
        ):
            gaps.append("source operand matching registry operand")

    trace = row.get(required_trace)
    if not isinstance(trace, Mapping):
        gaps.append(f"mapping-like {required_trace.replace('_', ' ')}")
    elif trace.get("benchmark_name") != row["name"]:
        gaps.append(f"{required_trace.replace('_', ' ')} benchmark identity")
    elif trace.get("source_sha256") != runtime_record.get("source_sha256"):
        gaps.append(f"{required_trace.replace('_', ' ')} source hash")

    extraction_trace = row.get("extraction_trace")
    if not isinstance(extraction_trace, Mapping):
        gaps.append("mapping-like extraction trace")
    elif extraction_trace.get("benchmark_name") != row["name"]:
        gaps.append("extraction trace benchmark identity")
    elif extraction_trace.get("source_sha256") != runtime_record.get("source_sha256"):
        gaps.append("extraction trace source hash")

    if expected_mode == "local_recompute" and isinstance(runtime_record, Mapping):
        execution_trace = row.get("execution_trace")
        if not isinstance(execution_trace, Mapping):
            gaps.append("mapping-like execution trace")
        elif not execution_trace.get("adapter"):
            gaps.append("nonempty execution adapter")
        elif execution_trace.get("computed_operand") != runtime_record.get(
            "computed_operand"
        ):
            gaps.append("execution trace computed operand")
        if runtime_record.get("computed_operand") != runtime_record.get(
            "source_operand"
        ):
            gaps.append("computed operand matching source operand")
    return gaps


def _assert_strict_yes_has_runtime_evidence(row, *, required_trace):
    gaps = _runtime_evidence_gaps(row, required_trace=required_trace)

    assert row["strict_literature_match_label"] != "yes" or not gaps, (
        f"{row['name']} was promoted to strict yes by local_check_kind="
        f"{row['local_check_kind']!r} without {', '.join(gaps)}"
    )


def _assert_legacy_projection_only(row):
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match"] is False
    assert row["strict_literature_match_label"] == "no"
    assert row["runtime_evidence_record"] is None
    assert row["execution_trace"] is None
    assert row["extraction_trace"] is None


def test_runtime_disabled_audit_keeps_every_legacy_row_non_strict():
    rows = build_literature_reproduction_audit()["rows"]

    strict_rows = [row for row in rows if row["strict_literature_match_label"] == "yes"]
    assert strict_rows == []
    for row in rows:
        _assert_legacy_projection_only(row)


def test_prose_only_evidence_cannot_yield_strict_yes_without_runtime_execution_evidence():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "majundar_ghosh_chain_exact_dimer_point"
    ]

    assert isinstance(row["local_check_evidence"], str)
    assert row["verification_task_count"] == 0
    _assert_strict_yes_has_runtime_evidence(row, required_trace="execution_trace")


def test_checked_only_evidence_cannot_yield_strict_yes_without_runtime_execution_evidence():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "zncu3oh6cl2_kagome_dzyaloshinskii_moriya_reference"
    ]

    assert "checked only" in row["local_check_evidence"].lower()
    _assert_strict_yes_has_runtime_evidence(row, required_trace="execution_trace")


def test_hard_coded_parse_helper_cannot_yield_strict_yes_without_runtime_extraction_evidence(
    monkeypatch,
):
    def fail_if_parser_is_called(*args, **kwargs):
        raise AssertionError("published-result parser must execute on the audit path")

    monkeypatch.setattr(
        literature_spin_model_benchmarks,
        "triangular_j1_j2_zhu_white_phase_sequence_status",
        fail_if_parser_is_called,
    )

    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "triangular_j1_j2_spin_half_phase_diagram_reference"
    ]

    assert row["local_check_kind"] == "published_dmrg_phase_sequence_parse"
    _assert_strict_yes_has_runtime_evidence(row, required_trace="extraction_trace")


def test_literature_audit_diagnostic_exposes_unsupported_strict_promotions():
    rows = build_literature_reproduction_audit()["rows"]

    def lacks_runtime_evidence(row):
        return bool(
            _runtime_evidence_gaps(row, required_trace="extraction_trace")
            and _runtime_evidence_gaps(row, required_trace="execution_trace")
        )

    strict_yes_rows = [
        row
        for row in rows
        if row["strict_literature_match_label"] == "yes" and lacks_runtime_evidence(row)
    ]
    diagnostics = {
        "whitelist_only_promotions": sorted(
            row["name"]
            for row in strict_yes_rows
            if row["strict_audit_category"] == "strict_local_recomputed"
        ),
        "zero_task_rows": sorted(
            row["name"]
            for row in strict_yes_rows
            if row["verification_task_count"] == 0
        ),
        "weak_marker_rows": sorted(
            row["name"]
            for row in strict_yes_rows
            if any(
                marker
                in f"{row['local_check_kind']} {row['local_check_evidence']}".lower()
                for marker in TEST_WEAK_EVIDENCE_MARKERS
            )
        ),
    }

    assert all(not names for names in diagnostics.values()), diagnostics


def test_literature_reproduction_audit_evidence_table_has_no_duplicate_names():
    audit_source = PROJECT_ROOT / "scripts" / "validation" / "literature_reproduction_audit.py"
    module = ast.parse(audit_source.read_text())

    keys = []
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "LOCAL_RECOMPUTED_EVIDENCE" for target in node.targets):
            continue
        keys = [
            key.value
            for key in node.value.keys
            if isinstance(key, ast.Constant)
        ]
        break

    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    assert duplicates == []


def test_literature_reproduction_audit_reports_disabled_runtime_subsets_separately():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    assert "strict_category_counts" in audit
    assert audit["total_standard_results"] == 155
    assert audit["category_counts"] == {
        "executable_projection": 0,
        "local_recomputed": 155,
        "reference_only": 0,
    }
    assert audit["strict_category_counts"] == {
        "executable_projection": 0,
        "local_projection_only": 155,
        "reference_only": 0,
        "strict_local_recomputed": 0,
        "strict_local_source_parsed": 0,
    }
    assert rows_by_name["majundar_ghosh_chain_exact_dimer_point"][
        "strict_audit_category"
    ] == "local_projection_only"
    assert rows_by_name["triangular_heisenberg_spin_half_energy_reference"][
        "strict_audit_category"
    ] == "local_projection_only"

    for name in {
        "herbertsmithite_kagome_qsl_reference",
        "ybmggao4_triangular_spin_liquid_reference",
    }:
        assert rows_by_name[name]["audit_category"] == "local_recomputed"
        assert rows_by_name[name]["strict_audit_category"] == "local_projection_only"

    assert rows_by_name["star_lattice_heisenberg_spin_liquid_reference"][
        "strict_audit_category"
    ] == "local_projection_only"

    assert rows_by_name["cu2oseo3_skyrmion_lattice_reference"][
        "strict_audit_category"
    ] == "local_projection_only"

    assert rows_by_name["square_spin_half_heisenberg_qmc_energy"][
        "strict_audit_category"
    ] == "local_projection_only"


def test_square_staggered_magnetization_retains_local_metadata_without_runtime_evidence_after_renormalized_formula_check():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "square_heisenberg_spin_half_staggered_magnetization_reference"
    ]

    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "renormalized_staggered_magnetization_formula"
    assert "M=S*Z_m" in row["local_check_evidence"]
    assert "0.30743" in row["local_check_evidence"]


def test_square_heisenberg_qmc_energy_retains_local_metadata_without_runtime_evidence_after_qmc_finite_size_extrapolation():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "square_spin_half_heisenberg_qmc_energy"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_qmc_finite_size_extrapolation"
    assert "E_inf=-0.669435659" in row["local_check_evidence"]
    assert "-0.669437 +/- 5e-6" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_cubic_ising_critical_temperature_retains_local_metadata_without_runtime_evidence_after_inverse_beta_conversion():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "cubic_ising_critical_temperature_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_critical_inverse_temperature_conversion"
    assert "beta_c=0.22165455" in row["local_check_evidence"]
    assert "T_c/J=4.511524803" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_xy_bkt_temperature_retains_local_metadata_without_runtime_evidence_after_inverse_beta_conversion():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "two_dimensional_xy_bkt_temperature_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_bkt_inverse_temperature_conversion"
    assert "beta_KT=1.1199" in row["local_check_evidence"]
    assert "T_BKT/J=0.892936869" in row["local_check_evidence"]
    assert "0.89294 +/- 5e-5" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_square_dimerized_heisenberg_critical_reference_retains_local_metadata_without_runtime_evidence_after_qmc_phase_boundary_conversion():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "square_dimerized_heisenberg_critical_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_qmc_phase_boundary_coordinate_conversion"
    assert "alpha_c=0.31407 at J'=1" in row["local_check_evidence"]
    assert "alpha_c=J'_c=0.52337" in row["local_check_evidence"]
    assert "R=0.343560658" in row["local_check_evidence"]
    assert "neel_to_dimer_transition=True" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_j1_j2_square_phase_window_retains_local_metadata_without_runtime_evidence_after_ccm_transition_window_rounding():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "j1_j2_square_spin_half_neel_collinear_transition_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_ccm_transition_window_rounding"
    assert "J2c1/J1=0.454" in row["local_check_evidence"]
    assert "J2c2/J1=0.588" in row["local_check_evidence"]
    assert "rounded outward to [0.4, 0.6]" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_triangular_j1_j2_phase_diagram_retains_local_metadata_without_runtime_evidence_after_zhu_white_phase_sequence_parse():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "triangular_j1_j2_spin_half_phase_diagram_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_dmrg_phase_sequence_parse"
    assert "0.06 <= J2/J1 <= 0.17" in row["local_check_evidence"]
    assert "120_degree -> spin_liquid -> stripe" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_triangular_j1_j2_spin_liquid_window_retains_local_metadata_without_runtime_evidence_after_dmrg_window_parse():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "j1_j2_triangular_spin_liquid_window_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_dmrg_spin_liquid_window_parse"
    assert "0.07 < J2/J1 < 0.15" in row["local_check_evidence"]
    assert "spin_liquid_window=[0.07, 0.15]" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_honeycomb_j1_j2_transition_retains_local_metadata_without_runtime_evidence_after_gong_dmrg_phase_text_parse():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "j1_j2_honeycomb_neel_spin_liquid_transition_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_dmrg_honeycomb_nonmagnetic_window_parse"
    assert "Neel order vanishing at J2/J1=0.22" in row["local_check_evidence"]
    assert "0.22 < J2/J1 < 0.25" in row["local_check_evidence"]
    assert "intermediate_nonmagnetic_phase=True" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_honeycomb_j1_j2_phase_reference_retains_local_metadata_without_runtime_evidence_after_gong_dmrg_phase_text_parse():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "honeycomb_spin_half_j1_j2_quantum_phase_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_dmrg_honeycomb_nonmagnetic_window_parse"
    assert "both spin and dimer orders vanish" in row["local_check_evidence"]
    assert "intermediate_nonmagnetic_phase_candidate=True" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_kagome_dm_critical_reference_retains_local_metadata_without_runtime_evidence_after_published_critical_ratio_parse():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "kagome_dzyaloshinskii_moriya_critical_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_ed_finite_size_dm_critical_ratio_parse"
    assert "D_c/J=0.1" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_kagome_heisenberg_tee_reference_retains_local_metadata_without_runtime_evidence_after_depenbrock_dmrg_parse():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "kagome_heisenberg_topological_entanglement_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_dmrg_topological_entanglement_parse"
    assert "gamma=log2(2)" in row["local_check_evidence"]
    assert "consistent_with_Z2" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_kagome_chiral_spin_liquid_reference_retains_local_metadata_without_runtime_evidence_after_bauer_topological_parse():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "kagome_chiral_spin_liquid_j1_j2_jchi_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_dmrg_chiral_spin_liquid_topological_diagnostic_parse"
    assert "ground-state degeneracy" in row["local_check_evidence"]
    assert "anyon" in row["local_check_evidence"]
    assert "chiral_spin_liquid_phase=True" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_square_j1_j2_vbs_reference_retains_local_metadata_without_runtime_evidence_after_gong_plaquette_vbs_parse():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "j1_j2_square_dqcp_columnar_vbs_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_dmrg_square_j1_j2_pvb_phase_parse"
    assert "0.5 < J2/J1 < 0.61" in row["local_check_evidence"]
    assert "columnar_or_plaquette_vbs_reference=True" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_square_j1_j2_j3_phase_reference_retains_local_metadata_without_runtime_evidence_after_peps_phase_text_parse():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "j1_j2_j3_square_quantum_phase_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_peps_square_j1_j2_j3_phase_diagram_parse"
    assert "gapless QSL" in row["local_check_evidence"]
    assert "plaquette VBS" in row["local_check_evidence"]
    assert "mixed columnar-plaquette VBS" in row["local_check_evidence"]
    assert "multiple_paramagnetic_regions=True" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_material_spin_liquid_references_retain_local_metadata_without_runtime_evidence_after_published_experimental_observable_parse():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}
    expected_names = {
        "herbertsmithite_kagome_qsl_reference",
        "tb2ti2o7_pyrochlore_spin_liquid_reference",
        "na4ir3o8_hyperkagome_material_reference",
        "ybmggao4_triangular_spin_liquid_reference",
        "scgo_kagome_bilayer_spin_liquid_reference",
        "garnet_gd3ga5o12_spin_liquid_reference",
        "h3liir2o6_kitaev_spin_liquid_candidate_reference",
        "ba3irti2o9_honeycomb_kitaev_reference",
    }

    for name in expected_names:
        row = rows_by_name[name]
        assert row["audit_category"] == "local_recomputed"
        assert row["strict_audit_category"] == "local_projection_only"
        assert row["strict_literature_match_label"] == "no"
        assert row["local_check_kind"] == "published_experimental_material_observable_parse"
        assert "direct published experimental observable" in row["local_check_evidence"]
        assert row["strict_reproduction_negative_evidence"] == ""


def test_kagome_j1_j2_phase_diagram_retains_local_metadata_without_runtime_evidence_after_kolley_phase_label_parse():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "kagome_j1_j2_heisenberg_phase_diagram_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_dmrg_phase_label_parse"
    assert "J2/J1 < -0.1 -> sqrt3xsqrt3_order" in row["local_check_evidence"]
    assert "-0.1 <= J2/J1 <= 0.2 -> spin_liquid" in row["local_check_evidence"]
    assert "J2/J1 > 0.2 -> q0_order" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_square_jq_deconfined_critical_reference_retains_local_metadata_without_runtime_evidence_after_sandvik_qmc_parse():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "square_jq_model_deconfined_critical_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "published_qmc_deconfined_transition_parse"
    assert "J/Q=0 -> VBS" in row["local_check_evidence"]
    assert "J/Q=0.1 -> Neel" in row["local_check_evidence"]
    assert "g_c=0.040 +/- 0.003" in row["local_check_evidence"]
    assert "z=1, nu=0.78, eta=0.26" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_kagome_spin_half_energy_retains_local_metadata_without_runtime_evidence_after_tenpy_idmrg_recompute():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "kagome_spin_half_heisenberg_energy_reference"
    ]

    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "infinite_mps_dmrg_energy"
    assert "TenPy infinite-cylinder DMRG" in row["local_check_evidence"]
    assert "-0.438244" in row["local_check_evidence"]
    assert "-0.4386 +/- 5e-4" in row["local_check_evidence"]


def test_yan_kagome_energy_gap_reference_retains_local_metadata_without_runtime_evidence_after_tenpy_gap_recompute():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "kagome_heisenberg_dmrg_spin_liquid_yan_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "tenpy_idmrg_energy_plus_finite_cylinder_spin_gap"
    assert "-0.438244" in row["local_check_evidence"]
    assert "Delta=0.116050" in row["local_check_evidence"]
    assert "0.13" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_checkerboard_plaquette_reference_retains_local_metadata_without_runtime_evidence_after_cyclic_plaquette_ed():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "checkerboard_heisenberg_plaquette_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "finite_cluster_plaquette_order_ed"
    assert "cyclic plaquette permutation" in row["local_check_evidence"]
    assert "Q_void=0.399194" in row["local_check_evidence"]
    assert "Q_crossed=-0.108133" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_star_lattice_reference_retains_local_metadata_without_runtime_evidence_after_betts_ed_recompute():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "star_lattice_heisenberg_spin_liquid_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "finite_cluster_star_lattice_ed"
    assert "18-site Betts star-lattice ED" in row["local_check_evidence"]
    assert "e_bond=-0.312478837" in row["local_check_evidence"]
    assert "Delta=0.578709898" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_triangular_ring_exchange_reference_retains_local_metadata_without_runtime_evidence_after_large_n_formula():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "triangular_ring_exchange_spin_liquid_reference"
    ]
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert row["local_check_kind"] == "large_n_mean_field_formula"
    assert "zero-flux spinon Fermi sea" in row["local_check_evidence"]
    assert "K/J=10.4" in row["local_check_evidence"]
    assert "E_zero=-0.253520" in row["local_check_evidence"]
    assert row["strict_reproduction_negative_evidence"] == ""


def test_remaining_strict_reproduction_gaps_report_uses_current_audit_counts(tmp_path):
    audit = build_literature_reproduction_audit()
    report_path = tmp_path / "remaining_strict_reproduction_gaps.md"
    write_remaining_strict_reproduction_gaps_markdown(audit, report_path)
    report_text = report_path.read_text(encoding="utf-8")

    strict_counts = audit["strict_category_counts"]
    strict_count = (
        strict_counts["strict_local_recomputed"]
        + strict_counts["strict_local_source_parsed"]
    )
    total_count = audit["total_standard_results"]

    assert strict_count == 0
    assert f"{strict_count} of {total_count}" in report_text
    assert "0 of 155 entries are strict runtime-evidenced entries" in report_text
    for category, count in strict_counts.items():
        assert f"- `{category}`: {count}" in report_text
    assert "The rows below remain `no`" in report_text
    assert "Count: 155" in report_text


def test_remaining_strict_reproduction_gaps_report_lists_missing_strict_evidence(
    tmp_path,
):
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}
    report_path = tmp_path / "remaining_strict_reproduction_gaps.md"
    write_remaining_strict_reproduction_gaps_markdown(audit, report_path)
    report_text = report_path.read_text(encoding="utf-8")

    square_j1j2_row = rows_by_name[
        "j1_j2_square_spin_half_neel_collinear_transition_reference"
    ]

    assert "strict_reproduction_gap_action" in square_j1j2_row
    assert square_j1j2_row["strict_reproduction_gap_action"] == (
        "To upgrade, replace `published_ccm_transition_window_rounding` with a direct "
        "local calculation of registered `quantum_phase_window` using `many_body` or "
        "an equivalent analytic/ED/GLT workflow."
    )
    assert "j1_j2_square_spin_half_neel_collinear_transition_reference" in report_text
    assert "registered `quantum_phase_window`" in report_text
    assert "square_spin_half_heisenberg_qmc_energy" in report_text
    assert "kagome_spin_half_heisenberg_energy_reference" in report_text
    assert "checkerboard_heisenberg_plaquette_reference" in report_text


def test_strict_reproduction_audit_preserves_legacy_metadata_for_remaining_gap_rows(
    tmp_path,
):
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}
    report_path = tmp_path / "remaining_strict_reproduction_gaps.md"
    write_remaining_strict_reproduction_gaps_markdown(audit, report_path)
    report_text = report_path.read_text(encoding="utf-8")

    square_energy = rows_by_name["square_spin_half_heisenberg_qmc_energy"]
    square_j1j2_window = rows_by_name[
        "j1_j2_square_spin_half_neel_collinear_transition_reference"
    ]
    square_staggered = rows_by_name[
        "square_heisenberg_spin_half_staggered_magnetization_reference"
    ]
    xy_bkt = rows_by_name["two_dimensional_xy_bkt_temperature_reference"]
    triangular_j1j2_phase = rows_by_name[
        "triangular_j1_j2_spin_half_phase_diagram_reference"
    ]
    triangular_j1j2_window = rows_by_name[
        "j1_j2_triangular_spin_liquid_window_reference"
    ]
    honeycomb_j1j2_phase = rows_by_name[
        "honeycomb_spin_half_j1_j2_quantum_phase_reference"
    ]
    kagome_dm = rows_by_name["kagome_dzyaloshinskii_moriya_critical_reference"]
    kagome_energy = rows_by_name["kagome_spin_half_heisenberg_energy_reference"]
    kagome_energy_gap = rows_by_name[
        "kagome_heisenberg_dmrg_spin_liquid_yan_reference"
    ]
    kagome_topological = rows_by_name[
        "kagome_heisenberg_topological_entanglement_reference"
    ]
    kagome_chiral = rows_by_name["kagome_chiral_spin_liquid_j1_j2_jchi_reference"]
    checkerboard = rows_by_name["checkerboard_heisenberg_plaquette_reference"]
    triangular_ring_exchange = rows_by_name[
        "triangular_ring_exchange_spin_liquid_reference"
    ]
    kagome_j1j2_phase = rows_by_name[
        "kagome_j1_j2_heisenberg_phase_diagram_reference"
    ]
    star_lattice = rows_by_name["star_lattice_heisenberg_spin_liquid_reference"]
    square_j1j2j3_phase = rows_by_name["j1_j2_j3_square_quantum_phase_reference"]
    herbertsmithite = rows_by_name["herbertsmithite_kagome_qsl_reference"]
    tb2ti2o7 = rows_by_name["tb2ti2o7_pyrochlore_spin_liquid_reference"]
    na4ir3o8 = rows_by_name["na4ir3o8_hyperkagome_material_reference"]
    square_jq_dqcp = rows_by_name["square_jq_model_deconfined_critical_reference"]
    square_j1j2_vbs = rows_by_name["j1_j2_square_dqcp_columnar_vbs_reference"]
    square_dimerized_qcp = rows_by_name[
        "square_dimerized_heisenberg_critical_reference"
    ]
    ybmggao4 = rows_by_name["ybmggao4_triangular_spin_liquid_reference"]
    scgo = rows_by_name["scgo_kagome_bilayer_spin_liquid_reference"]
    gdgagarnet = rows_by_name["garnet_gd3ga5o12_spin_liquid_reference"]
    h3liir2o6 = rows_by_name["h3liir2o6_kitaev_spin_liquid_candidate_reference"]
    ba3irti2o9 = rows_by_name["ba3irti2o9_honeycomb_kitaev_reference"]

    assert sum(row["strict_literature_match_label"] == "yes" for row in audit["rows"]) == 0
    assert sum(row["strict_literature_match_label"] == "no" for row in audit["rows"]) == 155
    assert all(row["strict_reproduction_negative_evidence"] == "" for row in audit["rows"])

    assert "strict_reproduction_negative_evidence" in square_energy
    assert square_energy["strict_literature_match_label"] == "no"
    assert "E_inf=-0.669435659" in square_energy["local_check_evidence"]
    assert "-0.669437 +/- 5e-6" in square_energy["local_check_evidence"]
    assert square_j1j2_window["strict_literature_match_label"] == "no"
    assert "rounded outward to [0.4, 0.6]" in square_j1j2_window["local_check_evidence"]
    assert square_staggered["strict_literature_match_label"] == "no"
    assert "M=S*Z_m" in square_staggered["local_check_evidence"]
    assert xy_bkt["strict_literature_match_label"] == "no"
    assert "T_BKT/J=0.892936869" in xy_bkt["local_check_evidence"]
    assert triangular_j1j2_phase["strict_literature_match_label"] == "no"
    assert "120_degree -> spin_liquid -> stripe" in triangular_j1j2_phase["local_check_evidence"]
    assert "spin_liquid_window=[0.07, 0.15]" in triangular_j1j2_window["local_check_evidence"]
    assert "0.22 < J2/J1 < 0.25" in honeycomb_j1j2_phase["local_check_evidence"]
    assert "D_c/J=0.1" in kagome_dm["local_check_evidence"]
    assert kagome_energy["strict_literature_match_label"] == "no"
    assert kagome_energy_gap["strict_literature_match_label"] == "no"
    assert kagome_energy_gap["strict_audit_category"] == "local_projection_only"
    assert "Delta=0.116050" in kagome_energy_gap["local_check_evidence"]
    assert "gamma=log2(2)" in kagome_topological["local_check_evidence"]
    assert "ground-state degeneracy" in kagome_chiral["local_check_evidence"]
    assert checkerboard["strict_literature_match_label"] == "no"
    assert triangular_ring_exchange["strict_literature_match_label"] == "no"
    assert kagome_j1j2_phase["strict_literature_match_label"] == "no"
    assert "J2/J1 > 0.2 -> q0_order" in kagome_j1j2_phase["local_check_evidence"]
    assert star_lattice["strict_literature_match_label"] == "no"
    assert "gapless QSL" in square_j1j2j3_phase["local_check_evidence"]
    assert "plaquette VBS" in square_j1j2j3_phase["local_check_evidence"]
    assert "direct published experimental observable" in herbertsmithite["local_check_evidence"]
    assert "direct published experimental observable" in tb2ti2o7["local_check_evidence"]
    assert "direct published experimental observable" in na4ir3o8["local_check_evidence"]
    assert square_jq_dqcp["strict_literature_match_label"] == "no"
    assert "g_c=0.040 +/- 0.003" in square_jq_dqcp["local_check_evidence"]
    assert "long-range plaquette" in square_j1j2_vbs["local_check_evidence"]
    assert square_dimerized_qcp["strict_literature_match_label"] == "no"
    assert "alpha_c=J'_c=0.52337" in square_dimerized_qcp["local_check_evidence"]
    assert "neel_to_dimer_transition=True" in square_dimerized_qcp["local_check_evidence"]
    assert "direct published experimental observable" in ybmggao4["local_check_evidence"]
    assert "direct published experimental observable" in scgo["local_check_evidence"]
    assert "direct published experimental observable" in gdgagarnet["local_check_evidence"]
    assert "direct published experimental observable" in h3liir2o6["local_check_evidence"]
    assert "direct published experimental observable" in ba3irti2o9["local_check_evidence"]
    cubic_ising_tc = rows_by_name["cubic_ising_critical_temperature_reference"]
    assert cubic_ising_tc["strict_literature_match_label"] == "no"
    assert "beta_c=0.22165455" in cubic_ising_tc["local_check_evidence"]
    assert "T_c/J=4.511524803" in cubic_ising_tc["local_check_evidence"]

    assert "Negative local attempts:" not in report_text
    for negative_evidence in {
        "-0.7017802",
        "second-order spin-wave",
        "-0.6684974",
        "4x4 J1-J2 square ED",
        "helicity-modulus scan",
        "L=24 crossing near T=0.9378",
        "6x3 triangular J1-J2 ED",
        "3x3 honeycomb J1-J2 ED",
        "12-site kagome DM ED scan",
        "gap minimum near D/J=0.05",
        "18-site periodic kagome ED",
        "E/N=-0.4471262",
        "triplet gap 0.2846",
        "toy q=0 peak absence",
        "triangle scalar-chirality spectrum",
        "4-site triangular ring-exchange ED",
        "nearest-neighbor kagome LT flat-band checks",
        "12-site kagome J1-J2 ED scan",
        "E/N=-0.4660540, -0.4537396, -0.4584631",
        "local frustrated star-lattice geometry check",
        "6-site star-lattice motif ED",
        "only nearby square J1-J2 finite-cluster trends",
        "classical J1-J2-J3 Fourier probe",
        "(0.4,0.3) selects an axial spiral candidate",
        "local kagome material QSL-candidate label check",
        "local pyrochlore material spin-liquid-candidate label check",
        "local tetrahedron ice-rule probe",
        "nearest-neighbor Ising correlation -1/3",
        "local hyperkagome material QSL-candidate label check",
        "No local J-Q QMC crossing",
        "4x4 periodic ring-exchange ED probe",
        "VBS structure factor rises from 0.06158 to 0.13767",
        "Neel structure factor falls from 0.27653 to 0.18994",
        "No local DMRG/VMC columnar-or-plaquette VBS diagnostic",
        "4x4 periodic J1-J2 ED probe",
        "VBS structure factors 0.09425, 0.10886, 0.09414",
        "No local dimerized-square QMC critical crossing",
        "4x4 columnar-dimer square ED scan",
        "local triangular anisotropic-exchange candidate label check",
        "local kagome-bilayer candidate label check",
        "local garnet short-range-order candidate label check",
        "local disordered honeycomb Kitaev candidate label check",
        "clean-limit Kitaev triangle-inequality probe",
        "local honeycomb Kitaev spin-liquid-candidate label check",
        "clean Kitaev limit exact-solution status",
        "honeycomb Curie-Weiss theta=-1",
        "small-L Wolff Binder scan",
        "L=8/10 crossing near T=4.4741",
    }:
        assert negative_evidence not in report_text


def test_square_staggered_magnetization_metadata_is_in_fresh_audit_and_gap_reports(
    tmp_path,
):
    audit = build_literature_reproduction_audit()
    remaining_gaps_path = tmp_path / "remaining_strict_reproduction_gaps.md"
    main_audit_path = tmp_path / "literature_reproduction_audit.md"
    write_remaining_strict_reproduction_gaps_markdown(audit, remaining_gaps_path)
    write_audit_markdown(audit, main_audit_path)
    remaining_gaps_text = remaining_gaps_path.read_text(encoding="utf-8")
    main_audit_text = main_audit_path.read_text(encoding="utf-8")

    assert "square_heisenberg_spin_half_staggered_magnetization_reference" in remaining_gaps_text
    assert "square_heisenberg_spin_half_staggered_magnetization_reference" in main_audit_text
    assert "renormalized_staggered_magnetization_formula" in main_audit_text


def test_literature_reproduction_audit_exposes_direct_literature_match_verdict():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    recomputed_row = rows_by_name["xxx_spin_half_chain_bethe_ground_state"]
    parsed_row = rows_by_name["cri3_honeycomb_ferromagnet_reference"]
    material_row = rows_by_name["herbertsmithite_kagome_qsl_reference"]
    square_qmc_row = rows_by_name["square_spin_half_heisenberg_qmc_energy"]
    stored_row = rows_by_name["j1_j2_square_spin_half_neel_collinear_transition_reference"]

    assert recomputed_row["strict_literature_match"] is False
    assert recomputed_row["strict_literature_match_label"] == "no"
    assert "Only a local projection" in recomputed_row[
        "strict_literature_match_reason"
    ]

    assert parsed_row["strict_literature_match"] is False
    assert parsed_row["strict_literature_match_label"] == "no"
    assert "Only a local projection" in parsed_row[
        "strict_literature_match_reason"
    ]

    assert material_row["strict_literature_match"] is False
    assert material_row["strict_literature_match_label"] == "no"
    assert "Only a local projection" in material_row[
        "strict_literature_match_reason"
    ]

    assert square_qmc_row["strict_literature_match"] is False
    assert square_qmc_row["strict_literature_match_label"] == "no"
    assert "Only a local projection" in square_qmc_row[
        "strict_literature_match_reason"
    ]

    assert stored_row["strict_literature_match"] is False
    assert stored_row["strict_literature_match_label"] == "no"
    assert "Only a local projection" in stored_row[
        "strict_literature_match_reason"
    ]


def test_literature_reproduction_audit_retains_formula_based_local_metadata():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    for name in {
        "fcc_j1_j2_heisenberg_type_order_reference",
        "bcc_j1_j2_heisenberg_collinear_reference",
        "honeycomb_j1_j2_j3_classical_phase_diagram",
    }:
        assert rows_by_name[name]["local_check_kind"] in {
            "fourier_exchange_formula",
            "classical_phase_formula",
        }
        assert rows_by_name[name]["strict_audit_category"] == "local_projection_only"


def test_literature_reproduction_audit_records_exact_limit_status_checks():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    for name in {
        "haldane_shastry_chain_exact_ground_state",
        "spin_ladder_rung_singlet_gap_reference",
        "honeycomb_haldane_kane_mele_hubbard_spin_model_reference",
        "spin_peierls_chain_dimerization_reference",
    }:
        assert rows_by_name[name]["audit_category"] == "local_recomputed"
        assert rows_by_name[name]["strict_audit_category"] == "local_projection_only"


def test_literature_reproduction_audit_records_quantum_spin_ice_strong_coupling_formula():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "quantum_spin_ice_u1_qsl_reference"
    ]

    assert row["local_check_kind"] == "strong_coupling_formula"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert "ring exchange" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_haldane_gap_infinite_mps_excitation():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "haldane_spin1_chain_gap_reference"
    ]

    assert row["local_check_kind"] == "infinite_mps_plane_wave_excitation"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert "Haldane gap" in row["local_check_evidence"]
    assert "TeNPy" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_kitaev_gamma_phase_content_scan():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "honeycomb_kitaev_gamma_phase_diagram_reference"
    ]

    assert row["local_check_kind"] == "classical_kitaev_gamma_phase_content_scan"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert "noncollinear" in row["local_check_evidence"]
    assert "zigzag" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_hyperkagome_triangle_constraint_calculation():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "hyperkagome_heisenberg_spin_liquid_reference"
    ]

    assert row["local_check_kind"] == "local_constraint_identity"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert "corner-sharing triangle" in row["local_check_evidence"]
    assert "underconstrained" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_triangular_xxz_supersolid_variational_formula():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "triangular_xxz_supersolid_phase_reference"
    ]

    assert row["local_check_kind"] == "classical_phase_formula"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert "canted uud" in row["local_check_evidence"]
    assert "supersolid" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_material_quantum_spin_ice_strong_coupling_formula():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "pr2zr2o7_quantum_spin_ice_reference"
    ]

    assert row["local_check_kind"] == "strong_coupling_formula"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert "ring exchange" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_spin_ice_material_pauling_entropy_formula():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "dy2ti2o7_spin_ice_entropy_reference"
    ]

    assert row["local_check_kind"] == "ideal_spin_ice_pauling_entropy_formula"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"


def test_literature_reproduction_audit_records_spin_ice_material_correlation_enumeration():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "ho2ti2o7_spin_ice_neutron_reference"
    ]

    assert row["local_check_kind"] == "spin_ice_ice_rule_correlation_enumeration"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"


def test_literature_reproduction_audit_records_parameterization_checks():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    row = rows_by_name["pyrochlore_anisotropic_exchange_jzz_jpm_reference"]

    assert row["local_check_kind"] == "anisotropic_exchange_parameterization"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"


def test_literature_reproduction_audit_records_local_energy_formula_checks():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    expected_kinds = {
        "licuvo4_spiral_chain_reference": "classical_j1_j2_chain_spiral_formula",
        "cs2cucl4_anisotropic_triangular_spiral_reference": "classical_anisotropic_triangular_spiral_formula",
        "zncu3oh6cl2_kagome_dzyaloshinskii_moriya_reference": "local_kagome_dm_chirality_relevance",
        "jarosite_kagome_dzyaloshinskii_moriya_reference": "local_classical_dm_limit",
    }

    for name, expected_kind in expected_kinds.items():
        assert rows_by_name[name]["local_check_kind"] == expected_kind
        assert rows_by_name[name]["audit_category"] == "local_recomputed"
        assert rows_by_name[name]["strict_audit_category"] == "local_projection_only"


def test_literature_reproduction_audit_records_okamoto_nomura_level_spectroscopy_ed():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "j1_j2_chain_okamoto_nomura_critical_point"
    ]

    assert row["local_check_kind"] == "finite_size_level_spectroscopy_ed"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"


def test_literature_reproduction_audit_records_j1_j2_chain_bkt_level_spectroscopy_ed():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "j1_j2_chain_bkt_transition_reference"
    ]

    assert row["local_check_kind"] == "finite_size_level_spectroscopy_ed"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"


def test_literature_reproduction_audit_records_strong_breathing_triangle_limit():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "breathing_kagome_heisenberg_reference"
    ]

    assert row["local_check_kind"] == "strong_breathing_triangle_ed"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"


def test_literature_reproduction_audit_records_classical_glt_order_limits():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    expected = {
        "haydeeite_ferromagnetic_kagome_reference": "classical_glt_order_limit",
        "crcl3_honeycomb_heisenberg_reference": "classical_glt_order_limit",
        "cri3_honeycomb_ferromagnet_reference": "classical_glt_order_limit",
        "crgete3_honeycomb_ferromagnet_reference": "classical_glt_order_limit",
        "fecl3_honeycomb_antiferromagnet_reference": "classical_glt_order_limit",
        "mn_ps3_honeycomb_antiferromagnet_reference": "classical_glt_order_limit",
        "ni_ps3_honeycomb_antiferromagnet_reference": "classical_honeycomb_j1_j3_zigzag_limit",
        "fe_ps3_honeycomb_ising_reference": "classical_honeycomb_j1_j3_zigzag_limit",
    }

    for name, expected_kind in expected.items():
        assert rows_by_name[name]["local_check_kind"] == expected_kind
        assert rows_by_name[name]["audit_category"] == "local_recomputed"
        assert rows_by_name[name]["strict_audit_category"] == (
            "local_projection_only"
        )
        assert rows_by_name[name]["strict_literature_match_label"] == "no"


def test_literature_reproduction_audit_records_pyrochlore_material_exchange_parameterization():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "yb2ti2o7_pyrochlore_exchange_reference"
    ]

    assert row["local_check_kind"] == "local_pyrochlore_anisotropic_exchange_label_set"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"


def test_literature_reproduction_audit_records_local_exchange_parameter_conditions():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    expected = {
        "kapellasite_kagome_j1_jd_reference": "local_kagome_j1_jd_competing_exchange_condition",
        "volborthite_kagome_distorted_reference": "local_distorted_kagome_exchange_inequivalence",
        "vesignieite_kagome_material_reference": "local_distorted_kagome_exchange_inequivalence",
        "clinoatacamite_distorted_kagome_reference": "local_distorted_kagome_exchange_inequivalence",
        "barlowite_kagome_material_reference": "local_kagome_interlayer_coupling_condition",
    }

    for name, expected_kind in expected.items():
        assert rows_by_name[name]["local_check_kind"] == expected_kind
        assert rows_by_name[name]["audit_category"] == "local_recomputed"
        assert rows_by_name[name]["strict_audit_category"] == "local_projection_only"


def test_literature_reproduction_audit_records_garnet_triangle_constraint_calculation():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    for name in {
        "gadolinium_gallium_garnet_hyperkagome_reference",
        "garnet_gd3te2li3o12_hyperkagome_reference",
    }:
        row = rows_by_name[name]
        assert row["local_check_kind"] == "local_constraint_identity"
        assert row["audit_category"] == "local_recomputed"
        assert row["strict_audit_category"] == "local_projection_only"
        assert row["strict_literature_match_label"] == "no"
        assert "corner-sharing triangle" in row["local_check_evidence"]
        assert "underconstrained" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_analytic_selector_and_field_window():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    expected = {
        "er2ti2o7_xy_pyrochlore_order_by_disorder_reference": "analytic_clock_anisotropy_selector",
        "bpcb_spin_ladder_field_induced_order_reference": "strong_rung_ladder_critical_field_formula",
    }

    for name, expected_kind in expected.items():
        assert rows_by_name[name]["local_check_kind"] == expected_kind
        assert rows_by_name[name]["audit_category"] == "local_recomputed"
        assert rows_by_name[name]["strict_audit_category"] == "local_projection_only"
        assert rows_by_name[name]["strict_literature_match_label"] == "no"


def test_literature_reproduction_audit_records_large_d_finite_size_ed_scan():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "spin1_chain_large_d_transition_reference"
    ]

    assert row["local_check_kind"] == "finite_size_large_d_transition_ed"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"


def test_literature_reproduction_audit_records_dimer_monomer_plateau_formula():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "azurite_diamond_chain_plateau_reference"
    ]

    assert row["local_check_kind"] == "strong_dimer_monomer_plateau_formula"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"


def test_literature_reproduction_audit_records_shastry_sutherland_dimer_plateau_formula():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "shastry_sutherland_magnetization_plateaus_reference"
    ]

    assert row["local_check_kind"] == "orthogonal_dimer_plateau_formula"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"


def test_literature_reproduction_audit_records_classical_material_model_limits():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    expected = {
        "li2cuo2_frustrated_ferromagnetic_chain_reference": "classical_j1_j2_chain_frustration_formula",
        "nacuo2_triangular_heisenberg_material_reference": "classical_triangular_nn_120_energy_formula",
        "edwardsite_kagome_antiferromagnet_reference": "local_kagome_120_constraint_formula",
    }

    for name, expected_kind in expected.items():
        assert rows_by_name[name]["local_check_kind"] == expected_kind
        assert rows_by_name[name]["audit_category"] == "local_recomputed"
        assert rows_by_name[name]["strict_audit_category"] == "local_projection_only"
        assert rows_by_name[name]["strict_literature_match_label"] == "no"


def test_literature_reproduction_audit_records_material_exchange_formula_limits():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    expected = {
        "cacu2o3_spin_ladder_reference": "strong_rung_ladder_exact_spectrum_formula",
        "sr_cu2_bo3_2_shastry_sutherland_material_reference": "orthogonal_dimer_material_plateau_formula",
        "zn_barlowite_kagome_qsl_reference": "local_kagome_interlayer_reduction_formula",
    }

    for name, expected_kind in expected.items():
        assert rows_by_name[name]["local_check_kind"] == expected_kind
        assert rows_by_name[name]["audit_category"] == "local_recomputed"
        assert rows_by_name[name]["strict_audit_category"] == "local_projection_only"
        assert rows_by_name[name]["strict_literature_match_label"] == "no"


def test_literature_reproduction_audit_records_triangular_lattice_material_plateau_ed():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "ba3cosb2o9_triangular_plateau_reference"
    ]

    assert row["local_check_kind"] == "triangular_lattice_plateau_finite_cluster_ed"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"


def test_literature_reproduction_audit_records_honeycomb_kitaev_material_zigzag_energy():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "honeycomb_j1_j2_kitaev_material_na2iro3_reference"
    ]

    assert row["local_check_kind"] == "honeycomb_kitaev_heisenberg_zigzag_energy_enumeration"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"


def test_literature_reproduction_audit_records_alpha_rucl3_kitaev_gamma_zigzag_energy():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "alpha_rucl3_kitaev_gamma_zigzag_reference"
    ]

    assert row["local_check_kind"] == "honeycomb_kitaev_gamma_zigzag_energy_enumeration"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"


def test_literature_reproduction_audit_records_li2iro3_kitaev_gamma_spiral_energy_formula():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    for name in {
        "beta_li2iro3_spiral_kitaev_gamma_reference",
        "gamma_li2iro3_3d_kitaev_reference",
    }:
        row = rows_by_name[name]
        assert row["local_check_kind"] == "single_q_anisotropic_exchange_spiral_formula"
        assert row["audit_category"] == "local_recomputed"
        assert row["strict_audit_category"] == "local_projection_only"
        assert row["strict_literature_match_label"] == "no"
        assert "single-q" in row["local_check_evidence"]
        assert "incommensurate" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_cu2oseo3_skyrmion_variational_minimization():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "cu2oseo3_skyrmion_lattice_reference"
    ]

    assert row["local_check_kind"] == "classical_chiral_skyrmion_lattice_variational_minimization"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert "triple-q" in row["local_check_evidence"]
    assert "topological charge" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_ca10_bilayer_breathing_kagome_glt_model():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "ca10cr7o28_bilayer_breathing_kagome_reference"
    ]

    assert row["local_check_kind"] == "classical_bilayer_breathing_kagome_exchange_glt"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert "Fourier exchange kernel" in row["local_check_evidence"]
    assert "mixed ferromagnetic/antiferromagnetic" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_li2iro3_hyperhoneycomb_kitaev_gamma_energy():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "li2iro3_hyperhoneycomb_kitaev_reference"
    ]

    assert row["local_check_kind"] == "single_q_anisotropic_exchange_spiral_formula"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert "hyperhoneycomb" in row["local_check_evidence"]
    assert "Kitaev-Gamma" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_ru_br3_honeycomb_kitaev_gamma_zigzag_energy():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "ru_br3_kitaev_material_reference"
    ]

    assert row["local_check_kind"] == "honeycomb_kitaev_gamma_zigzag_energy_enumeration"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert "RuBr3" in row["local_check_evidence"]
    assert "zigzag" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_cu2iro3_honeycomb_kh_energy():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "cu2iro3_honeycomb_kitaev_reference"
    ]

    assert row["local_check_kind"] == "honeycomb_kitaev_heisenberg_zigzag_energy_enumeration"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert "Cu2IrO3" in row["local_check_evidence"]
    assert "Kitaev-Heisenberg" in row["local_check_evidence"]
    assert "zigzag" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_shuriken_square_kagome_flat_band():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "shuriken_lattice_heisenberg_reference"
    ]

    assert row["local_check_kind"] == "flat_band_formula"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert "square-kagome" in row["local_check_evidence"]
    assert "localized-magnon" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_maple_leaf_glt_order():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "maple_leaf_lattice_heisenberg_reference"
    ]

    assert row["local_check_kind"] == "fourier_exchange_formula"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert "non-Gamma" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_square_velocity_spin_wave_formula():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "square_heisenberg_spin_wave_velocity_reference"
    ]

    assert row["local_check_kind"] == "renormalized_spin_wave_formula"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert "renormalized" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_square_stiffness_renormalized_series_formula():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "square_heisenberg_spin_half_spin_stiffness_reference"
    ]

    assert row["local_check_kind"] == "renormalized_spin_stiffness_formula"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert "rho_s=J*S^2*Z_rho" in row["local_check_evidence"]


def test_literature_reproduction_audit_records_square_ring_exchange_vbs_ed():
    audit = build_literature_reproduction_audit()
    row = {row["name"]: row for row in audit["rows"]}[
        "square_ring_exchange_neel_vbs_reference"
    ]

    assert row["local_check_kind"] == "finite_cluster_exact_diagonalization"
    assert row["audit_category"] == "local_recomputed"
    assert row["strict_audit_category"] == "local_projection_only"
    assert row["strict_literature_match_label"] == "no"
    assert "ring exchange" in row["local_check_evidence"]
    assert "VBS" in row["local_check_evidence"]


def test_literature_reproduction_audit_classifies_every_standard_result_once():
    audit = build_literature_reproduction_audit()
    rows = audit["rows"]
    names = [row["name"] for row in rows]

    assert audit["total_standard_results"] == 155
    assert len(rows) == audit["total_standard_results"]
    assert len(names) == len(set(names))
    assert set(audit["category_counts"]) == {
        "local_recomputed",
        "executable_projection",
        "reference_only",
    }
    assert sum(audit["category_counts"].values()) == audit["total_standard_results"]


def test_literature_reproduction_audit_keeps_strict_categories_honest():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    assert rows_by_name["majundar_ghosh_chain_exact_dimer_point"]["audit_category"] == "local_recomputed"
    assert rows_by_name["triangular_nn_classical_120_reference"]["audit_category"] == "local_recomputed"
    assert rows_by_name["haldane_spin1_chain_gap_reference"]["audit_category"] == "local_recomputed"
    assert rows_by_name["haldane_spin1_chain_gap_reference"][
        "strict_audit_category"
    ] == "local_projection_only"
    assert rows_by_name["square_spin_half_heisenberg_qmc_energy"]["audit_category"] == "local_recomputed"
    assert rows_by_name["square_spin_half_heisenberg_qmc_energy"][
        "strict_audit_category"
    ] == "local_projection_only"
    assert rows_by_name["kagome_spin_half_heisenberg_energy_reference"]["audit_category"] == "local_recomputed"
    assert rows_by_name["kagome_spin_half_heisenberg_energy_reference"][
        "strict_audit_category"
    ] == "local_projection_only"
    for name in {
        "bilinear_biquadratic_spin1_chain_aklt_angle",
        "one_dimensional_classical_ising_no_finite_t_transition",
        "one_dimensional_classical_ising_correlation_length",
        "lieb_schultz_mattis_half_integer_constraint",
        "eight_vertex_zero_field_exact_solution_status",
        "blume_capel_spin1_zero_temperature_level_crossing",
        "square_potts_exact_critical_point",
        "square_six_vertex_ice_exact_solution_status",
        "square_toric_code_exact_topological_degeneracy",
        "square_compass_model_directional_exchange_degeneracy",
        "square_ashkin_teller_exact_critical_line",
        "pyrochlore_dipolar_spin_ice_pauling_entropy",
        "sawtooth_chain_localized_magnon_flat_band",
        "diamond_chain_localized_magnon_flat_band",
        "lieb_lattice_heisenberg_ferrimagnet_reference",
        "xx_spin_half_chain_free_fermion_energy",
        "xy_spin_half_chain_anisotropic_critical_line",
        "lieb_liniger_delta_bose_gas_bethe_reference",
        "gaudin_yang_spin_half_fermion_bethe_reference",
        "triangular_ising_ferromagnet_exact_tc",
        "honeycomb_ising_ferromagnet_exact_tc",
        "kagome_ising_ferromagnet_exact_tc",
        "honeycomb_j1_j2_j3_classical_phase_diagram",
        "pyrochlore_anisotropic_exchange_jzz_jpm_reference",
        "takhtajan_babujian_spin1_critical_point",
        "uimin_lai_sutherland_spin1_su3_point",
        "quantum_spin_ice_u1_qsl_reference",
        "ruby_lattice_heisenberg_flat_band_reference",
        "haldane_shastry_chain_exact_ground_state",
        "honeycomb_haldane_kane_mele_hubbard_spin_model_reference",
        "spin_peierls_chain_dimerization_reference",
        "triangular_ising_antiferromagnet_residual_entropy",
        "square_fully_frustrated_ising_residual_entropy_reference",
        "kagome_ising_antiferromagnet_residual_entropy_reference",
        "fcc_j1_j2_heisenberg_type_order_reference",
        "bcc_j1_j2_heisenberg_collinear_reference",
        "kitaev_honeycomb_exact_spin_liquid_limit",
        "kitaev_honeycomb_abelian_nonabelian_field_gap_reference",
        "pyrochlore_heisenberg_coulomb_phase_flat_band",
        "pyrochlore_heisenberg_afm_coulomb_phase_reference",
        "checkerboard_heisenberg_afm_planar_pyrochlore_reference",
        "honeycomb_kitaev_heisenberg_four_sublattice_phases",
        "honeycomb_kitaev_gamma_phase_diagram_reference",
        "square_clock_q5_two_bkt_transitions",
        "spin_ladder_rung_singlet_gap_reference",
        "fe8_molecular_spin_tunneling_reference",
        "triangular_heisenberg_magnetization_plateau_reference",
        "kagome_one_third_magnetization_plateau_reference",
        "breathing_kagome_heisenberg_reference",
        "crcl3_honeycomb_heisenberg_reference",
        "cri3_honeycomb_ferromagnet_reference",
        "crgete3_honeycomb_ferromagnet_reference",
        "fecl3_honeycomb_antiferromagnet_reference",
        "mn_ps3_honeycomb_antiferromagnet_reference",
        "haydeeite_ferromagnetic_kagome_reference",
        "jarosite_kagome_dzyaloshinskii_moriya_reference",
        "alpha_rucl3_kitaev_gamma_zigzag_reference",
        "beta_li2iro3_spiral_kitaev_gamma_reference",
        "gamma_li2iro3_3d_kitaev_reference",
        "honeycomb_j1_j2_kitaev_material_na2iro3_reference",
        "zncu3oh6cl2_kagome_dzyaloshinskii_moriya_reference",
        "ba2cugeo7_dm_spiral_reference",
        "mnsi_chiral_helimagnet_reference",
        "dy2ti2o7_spin_ice_entropy_reference",
        "kapellasite_kagome_j1_jd_reference",
        "licuvo4_spiral_chain_reference",
        "cs2cucl4_anisotropic_triangular_spiral_reference",
        "ni_ps3_honeycomb_antiferromagnet_reference",
        "fe_ps3_honeycomb_ising_reference",
        "ba3cosb2o9_triangular_plateau_reference",
        "cacu2o3_spin_ladder_reference",
        "triangular_heisenberg_spin_half_energy_reference",
        "volborthite_kagome_distorted_reference",
        "vesignieite_kagome_material_reference",
        "clinoatacamite_distorted_kagome_reference",
        "barlowite_kagome_material_reference",
        "zn_barlowite_kagome_qsl_reference",
        "li2iro3_hyperhoneycomb_kitaev_reference",
        "ru_br3_kitaev_material_reference",
        "ho2ti2o7_spin_ice_neutron_reference",
        "checkerboard_heisenberg_plaquette_reference",
        "yb2ti2o7_pyrochlore_exchange_reference",
        "pr2zr2o7_quantum_spin_ice_reference",
        "gadolinium_gallium_garnet_hyperkagome_reference",
        "garnet_gd3te2li3o12_hyperkagome_reference",
        "spin1_chain_large_d_transition_reference",
        "sr_cu2_bo3_2_shastry_sutherland_material_reference",
        "herbertsmithite_kagome_qsl_reference",
        "tb2ti2o7_pyrochlore_spin_liquid_reference",
        "hyperkagome_heisenberg_spin_liquid_reference",
        "na4ir3o8_hyperkagome_material_reference",
        "ca10cr7o28_bilayer_breathing_kagome_reference",
        "cu2iro3_honeycomb_kitaev_reference",
        "scgo_kagome_bilayer_spin_liquid_reference",
        "garnet_gd3ga5o12_spin_liquid_reference",
        "h3liir2o6_kitaev_spin_liquid_candidate_reference",
        "ba3irti2o9_honeycomb_kitaev_reference",
        "cu2oseo3_skyrmion_lattice_reference",
        "star_lattice_heisenberg_spin_liquid_reference",
        "maple_leaf_lattice_heisenberg_reference",
        "shuriken_lattice_heisenberg_reference",
        "ybmggao4_triangular_spin_liquid_reference",
    }:
        assert rows_by_name[name]["audit_category"] == "local_recomputed"

    for row in audit["rows"]:
        if row["audit_category"] == "local_recomputed":
            assert row["local_check_kind"]
            assert row["local_check_evidence"]
        elif row["audit_category"] == "executable_projection":
            assert row["covered_computable_observables"]
            assert row["local_check_kind"] == ""
        else:
            assert row["local_check_kind"] == ""


def test_literature_reproduction_audit_keeps_recent_upgrade_evidence_specific():
    audit = build_literature_reproduction_audit()
    rows_by_name = {row["name"]: row for row in audit["rows"]}

    expected_kinds = {
        "jarosite_kagome_dzyaloshinskii_moriya_reference": "local_classical_dm_limit",
        "ba2cugeo7_dm_spiral_reference": "single_q_dm_pitch_formula",
        "mnsi_chiral_helimagnet_reference": "single_q_dm_pitch_formula",
        "licuvo4_spiral_chain_reference": "classical_j1_j2_chain_spiral_formula",
        "cs2cucl4_anisotropic_triangular_spiral_reference": "classical_anisotropic_triangular_spiral_formula",
    }

    for name, expected_kind in expected_kinds.items():
        assert rows_by_name[name]["local_check_kind"] == expected_kind
