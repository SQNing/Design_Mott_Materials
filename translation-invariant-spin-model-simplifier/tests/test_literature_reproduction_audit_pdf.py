import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "reports") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "reports"))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from generate_literature_reproduction_audit_pdf import build_reproduction_pdf_payload
from validation.literature_reproduction_audit import build_literature_reproduction_audit


def test_reproduction_audit_pdf_payload_uses_current_strict_audit_counts():
    audit = build_literature_reproduction_audit()
    payload = build_reproduction_pdf_payload()

    assert payload["total_standard_results"] == audit["total_standard_results"]
    assert payload["category_counts"] == audit["category_counts"]
    assert payload["strict_category_counts"] == audit["strict_category_counts"]
    assert payload["category_counts"]["local_recomputed"] == payload["total_standard_results"]
    assert payload["category_counts"]["executable_projection"] == 0
    assert payload["category_counts"]["reference_only"] == 0
    assert payload["strict_category_counts"]["strict_local_recomputed"] == payload["total_standard_results"]
    assert payload["strict_category_counts"]["local_projection_only"] == 0
    assert "Local geometry, material-context, candidate-label, and projection checks" in payload["scope_note"]
    assert payload["direct_answer"].startswith("Yes.")
    expected_count_text = (
        f"{audit['strict_category_counts']['strict_local_recomputed']} "
        f"of {audit['total_standard_results']}"
    )
    assert expected_count_text in payload["direct_answer"]


def test_reproduction_audit_pdf_payload_lists_recent_local_checks():
    payload = build_reproduction_pdf_payload()
    rows_by_name = {row["name"]: row for row in payload["rows"]}

    assert rows_by_name["dy2ti2o7_spin_ice_entropy_reference"]["audit_category"] == "local_recomputed"
    assert rows_by_name["dy2ti2o7_spin_ice_entropy_reference"]["strict_audit_category"] == (
        "strict_local_recomputed"
    )
    assert rows_by_name["ho2ti2o7_spin_ice_neutron_reference"]["audit_category"] == "local_recomputed"
    assert rows_by_name["ho2ti2o7_spin_ice_neutron_reference"]["strict_audit_category"] == (
        "strict_local_recomputed"
    )
    assert rows_by_name["mnsi_chiral_helimagnet_reference"]["audit_category"] == "local_recomputed"
    assert rows_by_name["mnsi_chiral_helimagnet_reference"]["strict_audit_category"] == (
        "strict_local_recomputed"
    )
    assert rows_by_name["cu2oseo3_skyrmion_lattice_reference"]["audit_category"] == "local_recomputed"
    assert rows_by_name["cu2oseo3_skyrmion_lattice_reference"]["strict_audit_category"] == (
        "strict_local_recomputed"
    )
    assert rows_by_name["cu2oseo3_skyrmion_lattice_reference"]["local_check_kind"] == (
        "classical_chiral_skyrmion_lattice_variational_minimization"
    )


def test_reproduction_audit_pdf_payload_includes_remaining_gap_details():
    payload = build_reproduction_pdf_payload()
    remaining_gap_rows = payload["remaining_gap_rows"]
    rows_by_name = {row["name"]: row for row in remaining_gap_rows}
    all_rows_by_name = {row["name"]: row for row in payload["rows"]}

    assert len(remaining_gap_rows) == (
        payload["total_standard_results"]
        - payload["strict_category_counts"]["strict_local_recomputed"]
    )
    assert remaining_gap_rows == []
    assert set(rows_by_name) == {
        row["name"] for row in payload["rows"] if row["strict_literature_match_label"] == "no"
    }
    assert rows_by_name == {}
    assert all(row["strict_literature_match_label"] == "yes" for row in payload["rows"])
    assert all(row["strict_reproduction_negative_evidence"] == "" for row in payload["rows"])

    square_jq_row = all_rows_by_name["square_jq_model_deconfined_critical_reference"]
    assert square_jq_row["strict_literature_match_label"] == "yes"
    assert "g_c=0.040 +/- 0.003" in square_jq_row["local_check_evidence"]

    ba3irti2o9_row = all_rows_by_name["ba3irti2o9_honeycomb_kitaev_reference"]
    assert ba3irti2o9_row["strict_literature_match_label"] == "yes"
    assert "direct published experimental observable" in ba3irti2o9_row["local_check_evidence"]

    assert "cubic_ising_critical_temperature_reference" not in rows_by_name
    cubic_row = all_rows_by_name["cubic_ising_critical_temperature_reference"]
    assert cubic_row["strict_literature_match_label"] == "yes"
    assert cubic_row["strict_audit_category"] == "strict_local_recomputed"
    assert "T_c/J=4.511524803" in cubic_row["local_check_evidence"]
    assert "kagome_heisenberg_dmrg_spin_liquid_yan_reference" not in rows_by_name
    yan_row = all_rows_by_name["kagome_heisenberg_dmrg_spin_liquid_yan_reference"]
    assert yan_row["strict_literature_match_label"] == "yes"
    assert yan_row["strict_audit_category"] == "strict_local_recomputed"
    assert "Delta=0.116050" in yan_row["local_check_evidence"]
