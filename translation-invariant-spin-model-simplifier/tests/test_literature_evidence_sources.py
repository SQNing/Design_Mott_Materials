import hashlib
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from validation import fetch_literature_evidence_sources as source_fetcher
from validation.literature_evidence_sources import (
    SourceEvidenceError,
    _validate_retrieval_metadata,
    arxiv_atom_identifier_matches,
    authoritative_route_for_identity,
    load_verified_source,
    validate_download_response,
    validate_work_identity_document,
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


def _repository_fixture(
    tmp_path,
    *,
    evidence_doi=DOI,
    evidence_arxiv_id="2401.01234",
    legacy_evidence_url=False,
):
    arxiv_id = "2401.01234"
    evidence_url = "https://api.openalex.org/works/W123456789"
    evidence = json.dumps(
        {
            "id": "https://openalex.org/W123456789",
            "doi": f"https://doi.org/{evidence_doi}",
            "locations": [
                {"pdf_url": f"https://arxiv.org/pdf/{evidence_arxiv_id}.pdf"}
            ],
        },
        sort_keys=True,
    ).encode("utf-8")
    route = _provisioning()
    route["expected_media_type"] = "application/xml"
    route["authoritative_retrieval_route"] = {
        "kind": "arxiv_author_manuscript_pdf",
        "url": f"https://export.arxiv.org/pdf/{arxiv_id}",
        "artifact_identifier": f"arxiv:{arxiv_id}",
        "work_identity_evidence": {
            "kind": "openalex_same_work_location",
            "url": evidence_url,
        },
    }
    provenance = _provenance()
    provenance["retrieval_metadata"].update(
        {
            "method": "arxiv_author_manuscript_pdf",
            "authoritative_origin": "author_repository",
            "immutable_artifact_identifier": f"arxiv:{arxiv_id}",
            "work_identity_evidence": {
                "kind": "openalex_same_work_location",
                "url": evidence_url,
                "payload_relative_path": "work-identity.json",
                "payload_sha256": hashlib.sha256(evidence).hexdigest(),
                "payload_byte_length": len(evidence),
            },
        }
    )
    if legacy_evidence_url:
        descriptor = provenance["retrieval_metadata"]["work_identity_evidence"]
        provenance["retrieval_metadata"]["work_identity_evidence"] = {
            "kind": descriptor["kind"],
            "url": "https://openalex.org/W123456789",
        }
    source_dir = _write_source(tmp_path, provenance=provenance)
    source_dir.joinpath("work-identity.json").write_bytes(evidence)
    if legacy_evidence_url:
        source_dir.joinpath("work-identity.provenance.json").write_text(
            json.dumps(descriptor, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return source_dir, route


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


def test_repository_loader_parses_hashed_same_work_identity_payload(tmp_path):
    source_dir, route = _repository_fixture(tmp_path)
    verified = load_verified_source(
        source_dir,
        expected_source=_expected_source(),
        provisioning_route=route,
    )
    assert verified.source_id == SOURCE_ID


def test_repository_loader_rejects_hashed_identity_payload_for_wrong_doi(tmp_path):
    source_dir, route = _repository_fixture(
        tmp_path, evidence_doi="10.1234/different-work"
    )
    with pytest.raises(SourceEvidenceError, match="canonical DOI"):
        load_verified_source(
            source_dir,
            expected_source=_expected_source(),
            provisioning_route=route,
        )


def test_repository_loader_rejects_hashed_identity_payload_for_wrong_artifact(
    tmp_path,
):
    source_dir, route = _repository_fixture(
        tmp_path, evidence_arxiv_id="2401.99999"
    )
    with pytest.raises(SourceEvidenceError, match="does not locate"):
        load_verified_source(
            source_dir,
            expected_source=_expected_source(),
            provisioning_route=route,
        )


def test_repository_loader_accepts_same_openalex_id_across_api_endpoint_migration(
    tmp_path,
):
    source_dir, route = _repository_fixture(tmp_path, legacy_evidence_url=True)
    verified = load_verified_source(
        source_dir,
        expected_source=_expected_source(),
        provisioning_route=route,
    )
    assert verified.source_id == SOURCE_ID


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


def test_publisher_specific_routes_cover_all_registry_sources_without_generic_doi():
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
        "arxiv_export_pdf": 4,
        "arxiv_author_manuscript_pdf": 14,
        "aps_harvest_pdf": 84,
        "elsevier_article_api_xml": 9,
        "nature_open_article_pdf": 6,
        "nature_article_pdf": 2,
        "springer_content_pdf": 1,
        "iop_article_pdf": 5,
        "epl_iop_article_pdf": 1,
        "science_article_pdf": 2,
        "aip_article_discovery": 3,
        "institutional_repository_pdf": 1,
        "acs_article_pdf": 1,
        "jpsj_article_pdf": 1,
    }
    assert all(route["kind"] != "doi_content_negotiation" for route in routes.values())
    assert sum(route["access_mode"] == "unattended" for route in routes.values()) == 109
    assert sum(route["expected_media_type"] == "application/xml" for route in routes.values()) == 9


def test_tasaki_lsm_source_uses_verified_arxiv_same_work_route():
    route = authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1007/s10955-017-1946-0"}
    )

    assert route == {
        "kind": "arxiv_author_manuscript_pdf",
        "url": "https://export.arxiv.org/pdf/1708.05186",
        "expected_media_type": "application/pdf",
        "access_mode": "unattended",
        "artifact_identifier": "arxiv:1708.05186",
        "work_identity_evidence": {
            "kind": "openalex_same_work_location",
            "url": "https://api.openalex.org/works/W2745733334",
        },
    }


@pytest.mark.parametrize(
    ("doi", "arxiv_id", "openalex_id"),
    [
        ("10.1140/epjb/e2006-00273-y", "cond-mat/0604023", "W1983899391"),
        ("10.1140/epjb/e2015-60113-7", "1505.07219", "W2115824467"),
    ],
)
def test_epj_sources_use_verified_arxiv_same_work_routes(
    doi,
    arxiv_id,
    openalex_id,
):
    route = authoritative_route_for_identity({"kind": "doi", "value": doi})

    assert route == {
        "kind": "arxiv_author_manuscript_pdf",
        "url": f"https://export.arxiv.org/pdf/{arxiv_id}",
        "expected_media_type": "application/pdf",
        "access_mode": "unattended",
        "artifact_identifier": f"arxiv:{arxiv_id}",
        "work_identity_evidence": {
            "kind": "openalex_same_work_location",
            "url": f"https://api.openalex.org/works/{openalex_id}",
        },
    }


def _osti_work_identity_document(
    *,
    doi="10.1021/cm504242t",
    fulltext_url="https://www.osti.gov/servlets/purl/1185798",
):
    return [
        {
            "title": (
                "Coupling of Crystal Structure and Magnetism in the Layered, "
                "Ferromagnetic Insulator CrI3"
            ),
            "doi": doi,
            "links": [
                {"rel": "citation", "href": "https://www.osti.gov/biblio/1185798"},
                {"rel": "fulltext", "href": fulltext_url},
            ],
        }
    ]


def _cri3_osti_route():
    return authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1021/cm504242t"}
    )


def test_cri3_source_uses_osti_institutional_repository_route():
    assert _cri3_osti_route() == {
        "kind": "institutional_repository_pdf",
        "url": "https://www.osti.gov/servlets/purl/1185798",
        "expected_media_type": "application/pdf",
        "access_mode": "unattended",
        "artifact_identifier": "osti:1185798",
        "work_identity_evidence": {
            "kind": "osti_same_work_fulltext",
            "url": "https://www.osti.gov/api/v1/records/1185798",
        },
    }


def test_osti_identity_document_binds_doi_to_retrieved_fulltext():
    validate_work_identity_document(
        _osti_work_identity_document(),
        identity={"kind": "doi", "value": "10.1021/cm504242t"},
        authoritative_route=_cri3_osti_route(),
        evidence_kind="osti_same_work_fulltext",
    )


def test_osti_identity_document_rejects_wrong_doi():
    with pytest.raises(SourceEvidenceError, match="canonical DOI"):
        validate_work_identity_document(
            _osti_work_identity_document(doi="10.1021/different-work"),
            identity={"kind": "doi", "value": "10.1021/cm504242t"},
            authoritative_route=_cri3_osti_route(),
            evidence_kind="osti_same_work_fulltext",
        )


def test_osti_identity_document_rejects_wrong_fulltext_url():
    with pytest.raises(SourceEvidenceError, match="does not locate"):
        validate_work_identity_document(
            _osti_work_identity_document(
                fulltext_url="https://www.osti.gov/servlets/purl/9999999"
            ),
            identity={"kind": "doi", "value": "10.1021/cm504242t"},
            authoritative_route=_cri3_osti_route(),
            evidence_kind="osti_same_work_fulltext",
        )


@pytest.mark.parametrize(
    ("identity_kind", "route_kind", "expected_origin"),
    [
        ("arxiv", "arxiv_export_pdf", "arxiv"),
        ("doi", "arxiv_author_manuscript_pdf", "author_repository"),
        ("doi", "aps_harvest_pdf", "publisher"),
    ],
)
def test_provenance_origin_tracks_actual_retrieval_route(
    monkeypatch,
    identity_kind,
    route_kind,
    expected_origin,
):
    monkeypatch.setattr(source_fetcher, "_pdftotext_version", lambda: "fixture")
    identity_value = "2401.01234" if identity_kind == "arxiv" else DOI
    source = {
        "source_id": SOURCE_ID,
        "canonical_identity": {
            "kind": identity_kind,
            "value": identity_value,
        },
        "canonical_url": (
            f"https://arxiv.org/abs/{identity_value}"
            if identity_kind == "arxiv"
            else CANONICAL_URL
        ),
    }
    route = {
        "authoritative_retrieval_route": {
            "kind": route_kind,
            "artifact_identifier": (
                f"arxiv:{identity_value}"
                if "arxiv" in route_kind
                else f"doi:{identity_value}"
            ),
            "work_identity_evidence": {
                "kind": "canonical_identity",
                "url": source["canonical_url"],
            },
        }
    }
    response = {
        "body": b"%PDF-fixture",
        "final_url": "https://example.test/source.pdf",
        "status": 200,
        "headers": {"content-type": "application/pdf"},
        "media_type": "application/pdf",
    }
    bibliographic = {
        "title": "Fixture",
        "authors": ["A. Author"],
        "venue": "Fixture venue",
        "publication_date": "2024-01-01",
    }

    provenance = source_fetcher._build_provenance(
        source,
        route,
        response,
        bibliographic,
        payload_name="source.pdf",
    )

    assert provenance["retrieval_metadata"]["authoritative_origin"] == expected_origin


def test_loader_rejects_retrieval_origin_that_disagrees_with_route():
    metadata = dict(_provenance()["retrieval_metadata"])
    metadata.update(
        {
            "method": "arxiv_author_manuscript_pdf",
            "authoritative_origin": "publisher",
            "immutable_artifact_identifier": "arxiv:2401.01234",
            "work_identity_evidence": {
                "kind": "openalex_same_work_location",
                "url": "https://api.openalex.org/works/W123456789",
            },
        }
    )
    route = {
        "authoritative_retrieval_route": {
            "kind": "arxiv_author_manuscript_pdf",
            "artifact_identifier": "arxiv:2401.01234",
            "work_identity_evidence": {
                "kind": "openalex_same_work_location",
                "url": "https://api.openalex.org/works/W123456789",
            },
        }
    }

    with pytest.raises(SourceEvidenceError, match="origin disagrees"):
        _validate_retrieval_metadata(
            metadata,
            _provenance()["source_identity"],
            route,
        )


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
            {"kind": "doi", "value": "10.1016/0304-8853(75)90113-5"},
            "elsevier_article_api_xml",
            "https://api.elsevier.com/content/article/doi/10.1016/0304-8853(75)90113-5",
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
        "artifact_identifier": (
            f"arxiv:{identity['value']}"
            if identity["kind"] == "arxiv"
            else f"doi:{identity['value']}"
        ),
        "work_identity_evidence": {
            "kind": "canonical_identity",
            "url": (
                f"https://arxiv.org/abs/{identity['value']}"
                if identity["kind"] == "arxiv"
                else f"https://doi.org/{identity['value']}"
            ),
        },
    }


def test_open_repository_route_binds_arxiv_artifact_to_same_doi_work():
    route = authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1016/j.aop.2005.10.005"}
    )
    assert route == {
        "kind": "arxiv_author_manuscript_pdf",
        "url": "https://export.arxiv.org/pdf/cond-mat/0506438",
        "expected_media_type": "application/pdf",
        "access_mode": "unattended",
        "artifact_identifier": "arxiv:cond-mat/0506438",
        "work_identity_evidence": {
            "kind": "openalex_same_work_location",
            "url": "https://api.openalex.org/works/W2141708961",
        },
    }


def test_spin_ice_science_doi_uses_verified_arxiv_author_manuscript_route():
    route = authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1126/science.1064761"}
    )
    assert route == {
        "kind": "arxiv_author_manuscript_pdf",
        "url": "https://export.arxiv.org/pdf/cond-mat/0201427",
        "expected_media_type": "application/pdf",
        "access_mode": "unattended",
        "artifact_identifier": "arxiv:cond-mat/0201427",
        "work_identity_evidence": {
            "kind": "openalex_same_work_location",
            "url": "https://api.openalex.org/works/W2128117725",
        },
    }


def test_open_publisher_route_records_oa_identity_evidence():
    route = authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1038/ncomms14113"}
    )
    assert route == {
        "kind": "nature_open_article_pdf",
        "url": "https://www.nature.com/articles/ncomms14113.pdf",
        "expected_media_type": "application/pdf",
        "access_mode": "unattended",
        "artifact_identifier": "doi:10.1038/ncomms14113",
        "work_identity_evidence": {
            "kind": "openalex_publisher_oa_location",
            "url": "https://api.openalex.org/works/W2591608240",
        },
    }


def test_corrected_crgete3_source_uses_canonical_iop_route():
    route = authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1088/0953-8984/7/1/008"}
    )
    assert route == {
        "kind": "iop_article_pdf",
        "url": "https://iopscience.iop.org/article/10.1088/0953-8984/7/1/008/pdf",
        "expected_media_type": "application/pdf",
        "access_mode": "challenge_or_institutional",
        "artifact_identifier": "doi:10.1088/0953-8984/7/1/008",
        "work_identity_evidence": {
            "kind": "canonical_identity",
            "url": "https://doi.org/10.1088/0953-8984/7/1/008",
        },
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
        {"kind": "doi", "value": "10.1016/0003-4916(61)90115-4"}
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


def test_download_validation_rejects_elsevier_coredata_without_article_body():
    route = authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1016/0003-4916(70)90270-8"}
    )
    body = b"""<?xml version='1.0'?>
    <full-text-retrieval-response xmlns='http://www.elsevier.com/xml/svapi/article/dtd'>
      <coredata><title>The one-dimensional Ising model</title>
      <doi>10.1016/0003-4916(70)90270-8</doi></coredata>
    </full-text-retrieval-response>"""
    with pytest.raises(SourceEvidenceError, match="article body"):
        validate_download_response(
            route,
            status=200,
            headers={"content-type": "application/xml;charset=UTF-8"},
            body=body,
            final_url=route["url"],
        )


@pytest.mark.parametrize(
    "body_element",
    [
        b"<body/>",
        b"<originalText></originalText>",
        b"<sections><section>   </section></sections>",
        b"<originalText><coredata><title>Metadata only</title></coredata></originalText>",
    ],
)
def test_download_validation_rejects_empty_elsevier_article_body(body_element):
    route = authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1016/0003-4916(70)90270-8"}
    )
    body = (
        b"<full-text-retrieval-response>"
        b"<coredata><title>Metadata title must not count as body</title></coredata>"
        + body_element
        + b"</full-text-retrieval-response>"
    )
    with pytest.raises(SourceEvidenceError, match="nonempty article body"):
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
