import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "reports") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "reports"))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import pytest

from generate_literature_reproduction_audit_pdf import build_reproduction_pdf_payload
from validation.literature_reproduction_audit import build_literature_reproduction_audit
from validation.literature_runtime_evidence import DEFAULT_CACHE_ROOT


def _source_cache_populated():
    return DEFAULT_CACHE_ROOT.is_dir() and any(DEFAULT_CACHE_ROOT.iterdir())


pytestmark = pytest.mark.skipif(
    not _source_cache_populated(),
    reason="requires populated local literature source cache",
)


def test_reproduction_audit_pdf_payload_uses_current_strict_audit_counts():
    audit = build_literature_reproduction_audit()
    payload = build_reproduction_pdf_payload()

    assert payload["total_standard_results"] == audit["total_standard_results"]
    assert payload["category_counts"] == audit["category_counts"]
    assert payload["strict_category_counts"] == audit["strict_category_counts"]
    assert payload["category_counts"]["local_recomputed"] == payload["total_standard_results"]
    assert payload["category_counts"]["executable_projection"] == 0
    assert payload["category_counts"]["reference_only"] == 0
    assert payload["strict_category_counts"]["strict_local_recomputed"] == 21
    assert payload["strict_category_counts"]["strict_local_source_parsed"] == 76
    assert payload["strict_category_counts"]["local_projection_only"] == 58
    assert payload["strict_match_count"] == 97
    assert payload["strict_category_order"][:2] == (
        "strict_local_recomputed",
        "strict_local_source_parsed",
    )
    assert "Local geometry, material-context, candidate-label, and projection checks" in payload["scope_note"]
    assert payload["direct_answer"].startswith("No.")
    expected_count_text = (
        f"{audit['runtime_evidence_coverage']['supported']} "
        f"of {audit['total_standard_results']}"
    )
    assert expected_count_text in payload["direct_answer"]


def test_reproduction_audit_pdf_payload_lists_recent_local_checks():
    payload = build_reproduction_pdf_payload()
    rows_by_name = {row["name"]: row for row in payload["rows"]}

    assert rows_by_name["dy2ti2o7_spin_ice_entropy_reference"]["audit_category"] == "local_recomputed"
    assert rows_by_name["dy2ti2o7_spin_ice_entropy_reference"]["strict_audit_category"] == (
        "local_projection_only"
    )
    assert rows_by_name["ho2ti2o7_spin_ice_neutron_reference"]["audit_category"] == "local_recomputed"
    assert rows_by_name["ho2ti2o7_spin_ice_neutron_reference"]["strict_audit_category"] == (
        "strict_local_source_parsed"
    )
    assert rows_by_name["mnsi_chiral_helimagnet_reference"]["audit_category"] == "local_recomputed"
    assert rows_by_name["mnsi_chiral_helimagnet_reference"]["strict_audit_category"] == (
        "local_projection_only"
    )
    assert rows_by_name["cu2oseo3_skyrmion_lattice_reference"]["audit_category"] == "local_recomputed"
    assert rows_by_name["cu2oseo3_skyrmion_lattice_reference"]["strict_audit_category"] == (
        "local_projection_only"
    )
    assert rows_by_name["cu2oseo3_skyrmion_lattice_reference"]["local_check_kind"] == (
        "classical_chiral_skyrmion_lattice_variational_minimization"
    )
    assert rows_by_name["square_potts_exact_critical_point"]["strict_audit_category"] == (
        "strict_local_recomputed"
    )
    assert rows_by_name["square_potts_exact_critical_point"][
        "strict_literature_match_label"
    ] == "yes"
    assert rows_by_name["square_clock_q5_two_bkt_transitions"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["square_clock_q5_two_bkt_transitions"][
        "strict_literature_match_label"
    ] == "yes"
    assert rows_by_name["square_ashkin_teller_exact_critical_line"][
        "strict_audit_category"
    ] == "strict_local_recomputed"
    assert rows_by_name["square_ashkin_teller_exact_critical_line"][
        "strict_literature_match_label"
    ] == "yes"
    assert rows_by_name["triangular_ising_antiferromagnet_residual_entropy"][
        "strict_audit_category"
    ] == "strict_local_recomputed"
    assert rows_by_name["xy_spin_half_chain_anisotropic_critical_line"][
        "strict_audit_category"
    ] == "strict_local_recomputed"
    assert rows_by_name["diamond_j1_j2_spiral_surface_reference"][
        "strict_audit_category"
    ] == "strict_local_recomputed"
    assert rows_by_name["pyrochlore_anisotropic_exchange_jzz_jpm_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["yb2ti2o7_pyrochlore_exchange_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name[
        "honeycomb_haldane_kane_mele_hubbard_spin_model_reference"
    ]["strict_audit_category"] == "strict_local_source_parsed"
    assert rows_by_name["spin_ice_tetrahedron_nn_ice_rule"][
        "strict_audit_category"
    ] == "strict_local_recomputed"
    assert rows_by_name["square_j1_j3_classical_lifshitz_reference"][
        "strict_audit_category"
    ] == "strict_local_recomputed"
    assert rows_by_name["j1_j2_j3_square_quantum_phase_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["j1_j2_square_dqcp_columnar_vbs_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    for source_name in (
        "pyrochlore_heisenberg_coulomb_phase_flat_band",
        "j1_j2_square_spin_half_neel_collinear_transition_reference",
        "tb2ti2o7_pyrochlore_spin_liquid_reference",
        "scgo_kagome_bilayer_spin_liquid_reference",
    ):
        assert rows_by_name[source_name]["strict_audit_category"] == (
            "strict_local_source_parsed"
        )
    assert rows_by_name[
        "kitaev_honeycomb_abelian_nonabelian_field_gap_reference"
    ]["strict_audit_category"] == "strict_local_recomputed"
    assert rows_by_name["checkerboard_heisenberg_plaquette_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["spin_peierls_chain_dimerization_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["bpcb_spin_ladder_field_induced_order_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["two_dimensional_xy_bkt_temperature_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["azurite_diamond_chain_plateau_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["ba3cosb2o9_triangular_plateau_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["kagome_one_third_magnetization_plateau_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["shastry_sutherland_magnetization_plateaus_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["sr_cu2_bo3_2_shastry_sutherland_material_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["cacu2o3_spin_ladder_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["ba2cugeo7_dm_spiral_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["triangular_heisenberg_spin_half_energy_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["jarosite_kagome_dzyaloshinskii_moriya_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["maple_leaf_lattice_heisenberg_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["alpha_rucl3_kitaev_gamma_zigzag_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["beta_li2iro3_spiral_kitaev_gamma_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["cs2cucl4_anisotropic_triangular_spiral_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["square_dimerized_heisenberg_critical_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["square_jq_model_deconfined_critical_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    assert rows_by_name["triangular_nn_classical_120_reference"][
        "strict_audit_category"
    ] == "strict_local_recomputed"
    assert rows_by_name["fecl3_honeycomb_antiferromagnet_reference"][
        "strict_audit_category"
    ] == "strict_local_source_parsed"
    for material_name in (
        "barlowite_kagome_material_reference",
        "haydeeite_ferromagnetic_kagome_reference",
        "na4ir3o8_hyperkagome_material_reference",
        "pr2zr2o7_quantum_spin_ice_reference",
        "ybmggao4_triangular_spin_liquid_reference",
        "zn_barlowite_kagome_qsl_reference",
    ):
        assert rows_by_name[material_name]["strict_audit_category"] == (
            "strict_local_source_parsed"
        )


def test_reproduction_audit_pdf_payload_includes_remaining_gap_details():
    payload = build_reproduction_pdf_payload()
    remaining_gap_rows = payload["remaining_gap_rows"]
    rows_by_name = {row["name"]: row for row in remaining_gap_rows}
    all_rows_by_name = {row["name"]: row for row in payload["rows"]}

    assert len(remaining_gap_rows) == (
        payload["total_standard_results"]
        - payload["strict_category_counts"]["strict_local_recomputed"]
        - payload["strict_category_counts"]["strict_local_source_parsed"]
    )
    assert set(rows_by_name) == {
        row["name"] for row in payload["rows"] if row["strict_literature_match_label"] == "no"
    }
    assert len(rows_by_name) == 58

    square_jq_row = all_rows_by_name["square_jq_model_deconfined_critical_reference"]
    assert square_jq_row["strict_literature_match_label"] == "yes"
    assert square_jq_row["strict_audit_category"] == "strict_local_source_parsed"
    assert "square_jq_model_deconfined_critical_reference" not in rows_by_name
    assert "g_c=0.040 +/- 0.003" in square_jq_row["local_check_evidence"]

    for strict_source_name in (
        "alpha_rucl3_kitaev_gamma_zigzag_reference",
        "beta_li2iro3_spiral_kitaev_gamma_reference",
        "cs2cucl4_anisotropic_triangular_spiral_reference",
        "square_dimerized_heisenberg_critical_reference",
        "square_clock_q5_two_bkt_transitions",
        "square_ashkin_teller_exact_critical_line",
        "fecl3_honeycomb_antiferromagnet_reference",
        "triangular_nn_classical_120_reference",
        "honeycomb_haldane_kane_mele_hubbard_spin_model_reference",
        "j1_j2_j3_square_quantum_phase_reference",
        "j1_j2_square_dqcp_columnar_vbs_reference",
        "square_j1_j3_classical_lifshitz_reference",
        "spin_ice_tetrahedron_nn_ice_rule",
        "yb2ti2o7_pyrochlore_exchange_reference",
        "pyrochlore_heisenberg_coulomb_phase_flat_band",
        "j1_j2_square_spin_half_neel_collinear_transition_reference",
        "tb2ti2o7_pyrochlore_spin_liquid_reference",
        "scgo_kagome_bilayer_spin_liquid_reference",
    ):
        assert strict_source_name not in rows_by_name

    ba3irti2o9_row = all_rows_by_name["ba3irti2o9_honeycomb_kitaev_reference"]
    assert ba3irti2o9_row["strict_literature_match_label"] == "no"
    assert "direct published experimental observable" in ba3irti2o9_row["local_check_evidence"]

    assert "cubic_ising_critical_temperature_reference" in rows_by_name
    cubic_row = all_rows_by_name["cubic_ising_critical_temperature_reference"]
    assert cubic_row["strict_literature_match_label"] == "no"
    assert cubic_row["strict_audit_category"] == "local_projection_only"
    assert "T_c/J=4.511524803" in cubic_row["local_check_evidence"]
    assert "kagome_heisenberg_dmrg_spin_liquid_yan_reference" in rows_by_name
    yan_row = all_rows_by_name["kagome_heisenberg_dmrg_spin_liquid_yan_reference"]
    assert yan_row["strict_literature_match_label"] == "no"
    assert yan_row["strict_audit_category"] == "local_projection_only"
    assert "Delta=0.116050" in yan_row["local_check_evidence"]
