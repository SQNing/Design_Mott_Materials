import hashlib
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from validation.literature_evidence_sources import (
    SourceEvidenceError,
    arxiv_atom_identifier_matches,
    authoritative_route_for_identity,
    load_verified_source,
    validate_download_response,
)
from validation.literature_evidence_inventory import load_and_validate_inventory


SOURCE_ID = "doi_fixture_source"
DOI = "10.1234/example.1"
CANONICAL_URL = f"https://doi.org/{DOI}"
PAYLOAD = (
    b"<article><title>Exact observable study</title>"
    b"<p>The target observable is reported in the thermodynamic limit.</p></article>"
)


def _provenance(payload=PAYLOAD):
    return {
        "schema_version": 1,
        "source_id": SOURCE_ID,
        "source_identity": {
            "kind": "doi",
            "value": DOI,
            "canonical_url": CANONICAL_URL,
        },
        "bibliographic_metadata": {
            "title": "Exact observable study",
            "authors": ["A. Author", "B. Author"],
            "venue": "Journal of Test Physics",
            "publication_date": "2024-01-15",
        },
        "retrieval_metadata": {
            "url": "https://publisher.example/articles/example.1/fulltext.xml",
            "retrieved_at": "2026-07-17T12:00:00+08:00",
            "method": "doi_content_negotiation",
            "authoritative_origin": "publisher",
            "http_status": 200,
            "response_headers": {"content-type": "application/xml"},
            "immutable_artifact_identifier": f"doi:{DOI}",
        },
        "media_type": "application/xml",
        "raw_payload_sha256": hashlib.sha256(payload).hexdigest(),
        "raw_payload_byte_length": len(payload),
        "payload_relative_path": "payload.xml",
        "artifact_coordinates": {
            "kind": "whole_payload",
            "start_byte": 0,
            "end_byte": len(payload),
        },
        "license_access_notes": {
            "access_status": "open",
            "redistributability": "fixture_only",
            "notes": "Synthetic authoritative-route fixture for loader tests.",
        },
        "citation_metadata_verification": {
            "status": "verified",
            "verified_fields": ["title", "authors", "doi"],
        },
        "text_extraction": {
            "tool": "xml_text_content",
            "version": "python-stdlib",
            "deterministic": True,
        },
    }


def _expected_source():
    return {
        "source_id": SOURCE_ID,
        "canonical_identity": {"kind": "doi", "value": DOI},
        "canonical_url": CANONICAL_URL,
        "benchmark_names": ["fixture_benchmark"],
    }


def _provisioning():
    return {
        "source_id": SOURCE_ID,
        "authoritative_retrieval_route": {
            "kind": "doi_content_negotiation",
            "url": CANONICAL_URL,
        },
        "expected_media_type": "application/xml",
        "redistributability": "unresolved",
        "local_cache_location": f"source-cache/{SOURCE_ID}/source.pdf",
        "current_availability": "not_acquired",
    }


def _write_source(tmp_path, provenance=None, payload=PAYLOAD):
    source_dir = tmp_path / SOURCE_ID
    source_dir.mkdir(parents=True)
    source_dir.joinpath("payload.xml").write_bytes(payload)
    source_dir.joinpath("provenance.json").write_text(
        json.dumps(provenance or _provenance(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return source_dir


def _minimal_pdf(text):
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def _pdftotext_version():
    completed = subprocess.run(
        ["pdftotext", "-v"], capture_output=True, text=True, check=True
    )
    first_line = (completed.stderr or completed.stdout).splitlines()[0]
    return first_line.removeprefix("pdftotext version ").strip()


def test_offline_loader_verifies_authoritative_payload_without_network(
    tmp_path, monkeypatch
):
    source_dir = _write_source(tmp_path)

    def reject_network(*args, **kwargs):
        raise AssertionError("offline source loading attempted network access")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    verified = load_verified_source(
        source_dir,
        expected_source=_expected_source(),
        provisioning_route=_provisioning(),
        required_search_anchors=("target observable", "thermodynamic limit"),
    )

    assert verified.source_id == SOURCE_ID
    assert verified.payload_bytes == PAYLOAD
    assert "target observable" in verified.extracted_text
    assert verified.payload_sha256 == hashlib.sha256(PAYLOAD).hexdigest()
    assert verified.extraction_tool == {
        "tool": "xml_text_content",
        "version": "python-stdlib",
        "deterministic": True,
    }


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("bibliographic_metadata", "title"),
        ("bibliographic_metadata", "authors"),
        ("bibliographic_metadata", "venue"),
        ("bibliographic_metadata", "publication_date"),
        ("retrieval_metadata", "url"),
        ("retrieval_metadata", "retrieved_at"),
        ("retrieval_metadata", "method"),
        ("retrieval_metadata", "http_status"),
        ("retrieval_metadata", "immutable_artifact_identifier"),
        ("artifact_coordinates", "start_byte"),
        ("text_extraction", "version"),
    ],
)
def test_loader_rejects_incomplete_provenance(tmp_path, section, field):
    provenance = _provenance()
    del provenance[section][field]
    source_dir = _write_source(tmp_path, provenance=provenance)

    with pytest.raises(SourceEvidenceError, match=field):
        load_verified_source(
            source_dir,
            expected_source=_expected_source(),
            provisioning_route=_provisioning(),
            required_search_anchors=("target observable",),
        )


def test_loader_rejects_empty_or_hash_mismatched_payload(tmp_path):
    source_dir = _write_source(tmp_path, payload=b"")
    with pytest.raises(SourceEvidenceError, match="empty payload"):
        load_verified_source(
            source_dir,
            expected_source=_expected_source(),
            provisioning_route=_provisioning(),
            required_search_anchors=("target observable",),
        )

    source_dir = _write_source(tmp_path / "hash", provenance=_provenance())
    source_dir.joinpath("payload.xml").write_bytes(PAYLOAD + b"mutated")
    with pytest.raises(SourceEvidenceError, match="SHA-256"):
        load_verified_source(
            source_dir,
            expected_source=_expected_source(),
            provisioning_route=_provisioning(),
            required_search_anchors=("target observable",),
        )


def test_loader_rejects_source_identity_or_registry_url_disagreement(tmp_path):
    provenance = _provenance()
    provenance["source_identity"]["value"] = "10.1234/wrong"
    source_dir = _write_source(tmp_path, provenance=provenance)

    with pytest.raises(SourceEvidenceError, match="source identity"):
        load_verified_source(
            source_dir,
            expected_source=_expected_source(),
            provisioning_route=_provisioning(),
            required_search_anchors=("target observable",),
        )


def test_loader_rejects_manually_authored_payload_provenance(tmp_path):
    provenance = _provenance()
    provenance["retrieval_metadata"]["method"] = "manual_copy"
    provenance["retrieval_metadata"]["authoritative_origin"] = "local_author"
    source_dir = _write_source(tmp_path, provenance=provenance)

    with pytest.raises(SourceEvidenceError, match="authoritative retrieval"):
        load_verified_source(
            source_dir,
            expected_source=_expected_source(),
            provisioning_route=_provisioning(),
            required_search_anchors=("target observable",),
        )


def test_loader_rejects_metadata_or_payload_without_target_observable(tmp_path):
    payload = b"<article><title>Exact observable study</title><p>Metadata only.</p></article>"
    source_dir = _write_source(tmp_path, payload=payload)

    with pytest.raises(SourceEvidenceError, match="target-bearing anchor"):
        load_verified_source(
            source_dir,
            expected_source=_expected_source(),
            provisioning_route=_provisioning(),
            required_search_anchors=("target observable",),
        )


def test_pdf_loader_runs_recorded_pdftotext_version_and_finds_target(tmp_path):
    payload = _minimal_pdf("Target observable appears on PDF page one.")
    provenance = _provenance(payload)
    provenance["media_type"] = "application/pdf"
    provenance["payload_relative_path"] = "payload.pdf"
    provenance["retrieval_metadata"]["response_headers"] = {
        "content-type": "application/pdf"
    }
    provenance["text_extraction"] = {
        "tool": "pdftotext",
        "version": _pdftotext_version(),
        "deterministic": True,
        "arguments": ["-layout", "-enc", "UTF-8"],
    }
    provisioning = _provisioning()
    provisioning["expected_media_type"] = "application/pdf"
    source_dir = _write_source(tmp_path, provenance=provenance, payload=payload)
    source_dir.joinpath("payload.xml").rename(source_dir / "payload.pdf")

    verified = load_verified_source(
        source_dir,
        expected_source=_expected_source(),
        provisioning_route=provisioning,
        required_search_anchors=("target observable", "PDF page one"),
    )

    assert "Target observable appears on PDF page one." in verified.extracted_text
    assert verified.extraction_tool["tool"] == "pdftotext"
    assert verified.extraction_tool["version"] == _pdftotext_version()


def test_pdf_loader_rejects_unrecorded_extractor_version(tmp_path):
    payload = _minimal_pdf("Target observable appears on PDF page one.")
    provenance = _provenance(payload)
    provenance["media_type"] = "application/pdf"
    provenance["payload_relative_path"] = "payload.pdf"
    provenance["retrieval_metadata"]["response_headers"] = {
        "content-type": "application/pdf"
    }
    provenance["text_extraction"] = {
        "tool": "pdftotext",
        "version": "0.0-forged",
        "deterministic": True,
        "arguments": ["-layout", "-enc", "UTF-8"],
    }
    provisioning = _provisioning()
    provisioning["expected_media_type"] = "application/pdf"
    source_dir = _write_source(tmp_path, provenance=provenance, payload=payload)
    source_dir.joinpath("payload.xml").rename(source_dir / "payload.pdf")

    with pytest.raises(SourceEvidenceError, match="pdftotext version"):
        load_verified_source(
            source_dir,
            expected_source=_expected_source(),
            provisioning_route=provisioning,
            required_search_anchors=("target observable",),
        )


def test_publisher_specific_routes_cover_all_133_sources_without_generic_doi():
    inventory = load_and_validate_inventory()
    routes = {
        source["source_id"]: authoritative_route_for_identity(
            source["canonical_identity"]
        )
        for source in inventory.source_index
    }
    counts = {}
    for route in routes.values():
        counts[route["kind"]] = counts.get(route["kind"], 0) + 1

    assert counts == {
        "arxiv_export_pdf": 3,
        "aps_harvest_pdf": 77,
        "elsevier_article_api_xml": 12,
        "nature_article_pdf": 10,
        "springer_content_pdf": 2,
        "epj_springer_content_pdf": 2,
        "iop_article_pdf": 8,
        "epl_iop_article_pdf": 3,
        "science_article_pdf": 5,
        "aip_article_discovery": 4,
        "acs_article_pdf": 3,
        "jpsj_article_pdf": 3,
        "wiley_book_provisioning": 1,
    }
    assert all(route["kind"] != "doi_content_negotiation" for route in routes.values())
    assert sum(route["access_mode"] == "unattended" for route in routes.values()) == 80
    assert sum(route["expected_media_type"] == "application/xml" for route in routes.values()) == 12


@pytest.mark.parametrize(
    ("identity", "kind", "url", "media_type", "access_mode"),
    [
        (
            {"kind": "arxiv", "value": "1409.0193"},
            "arxiv_export_pdf",
            "https://export.arxiv.org/pdf/1409.0193",
            "application/pdf",
            "unattended",
        ),
        (
            {"kind": "doi", "value": "10.1103/physrevlett.59.799"},
            "aps_harvest_pdf",
            "https://harvest.aps.org/v2/journals/articles/10.1103/physrevlett.59.799/fulltext",
            "application/pdf",
            "unattended",
        ),
        (
            {"kind": "doi", "value": "10.1016/j.aop.2005.10.005"},
            "elsevier_article_api_xml",
            "https://api.elsevier.com/content/article/doi/10.1016/j.aop.2005.10.005",
            "application/xml",
            "api_key_or_entitlement",
        ),
        (
            {"kind": "doi", "value": "10.1002/9780470316517"},
            "wiley_book_provisioning",
            "https://doi.org/10.1002/9780470316517",
            "application/pdf",
            "licensed_manual_provisioning",
        ),
    ],
)
def test_representative_authoritative_routes_are_exact(
    identity, kind, url, media_type, access_mode
):
    assert authoritative_route_for_identity(identity) == {
        "kind": kind,
        "url": url,
        "expected_media_type": media_type,
        "access_mode": access_mode,
    }


def test_download_validation_rejects_html_challenge_even_with_status_200():
    route = authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1103/physrevlett.59.799"}
    )
    with pytest.raises(SourceEvidenceError, match="media type"):
        validate_download_response(
            route,
            status=200,
            headers={"content-type": "text/html; charset=UTF-8"},
            body=b"<html>challenge</html>",
            final_url="https://validate.example/challenge",
        )


@pytest.mark.parametrize(
    "body",
    [
        b"not-a-pdf" + b"x" * 512,
        b"%PDF-1.4\nshort",
    ],
)
def test_download_validation_rejects_invalid_or_truncated_pdf(body):
    route = authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1103/physrevlett.59.799"}
    )
    with pytest.raises(SourceEvidenceError, match="PDF"):
        validate_download_response(
            route,
            status=200,
            headers={"content-type": "application/pdf"},
            body=body,
            final_url=route["url"],
        )


def test_download_validation_accepts_real_pdf_shape():
    route = authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1103/physrevlett.59.799"}
    )
    body = _minimal_pdf("Target observable appears on PDF page one.")
    assert validate_download_response(
        route,
        status=200,
        headers={"content-type": "application/pdf"},
        body=body,
        final_url=route["url"],
    ) == "application/pdf"


def test_download_validation_rejects_elsevier_minimized_metadata_xml():
    route = authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1016/j.aop.2005.10.005"}
    )
    body = (
        b"<response><warning>Unauthorized request results in minimized metadata "
        b"response</warning></response>"
    )
    with pytest.raises(SourceEvidenceError, match="minimized metadata"):
        validate_download_response(
            route,
            status=200,
            headers={"content-type": "application/xml;charset=UTF-8"},
            body=body,
            final_url=route["url"],
        )


def test_arxiv_atom_identity_accepts_only_versioned_form_of_same_base_id():
    assert arxiv_atom_identifier_matches(
        "http://arxiv.org/abs/1409.0193v2", "1409.0193"
    )
    assert arxiv_atom_identifier_matches(
        "https://arxiv.org/abs/cond-mat/0612001v3", "cond-mat/0612001"
    )
    assert not arxiv_atom_identifier_matches(
        "https://arxiv.org/abs/1409.0194v2", "1409.0193"
    )
