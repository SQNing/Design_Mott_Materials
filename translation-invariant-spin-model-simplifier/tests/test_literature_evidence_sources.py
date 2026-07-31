from collections import Counter
import copy
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from validation import fetch_literature_evidence_sources as source_fetcher
from validation import literature_evidence_sources as evidence_sources
from validation.literature_evidence_sources import (
    SourceEvidenceError,
    _validate_retrieval_metadata,
    arxiv_atom_identifier_matches,
    authoritative_route_for_identity,
    load_verified_source,
    validate_download_response,
    validate_work_identity_document,
)
from validation.literature_evidence_inventory import (
    canonical_source_identity,
)
from validation.literature_spin_model_benchmarks import LITERATURE_STANDARD_RESULTS


SOURCE_ID = "doi_fixture_source"
DOI = "10.1234/example.1"
CANONICAL_URL = f"https://doi.org/{DOI}"
OUP_DOI = b"10.1143/ptp.5.2.177"
OUP_RESOLVER = b"https://doi.org/" + OUP_DOI
PAYLOAD = (
    b"<article><title>Exact observable study</title>"
    b"<p>The target observable is reported in the thermodynamic limit.</p></article>"
)
OUP_HTML = b"""<!doctype html>
<html lang="en">
  <head>
    <title>The Statistics of Honeycomb and Triangular Lattice. I</title>
    <style>.hidden-css-sentinel { display: none }</style>
    <script>window.javascript_hidden_sentinel = true;</script>
  </head>
  <body>
    <!-- comment-hidden-sentinel -->
    <article data-private="attribute-hidden-sentinel">
      <h1>The Statistics of Honeycomb and Triangular Lattice. I</h1>
      <p class="authors">Kodi Husimi and Itiro Syozi</p>
      <p>https://doi.org/10.1143/ptp.5.2.177</p>
      <section><h2>Summary</h2>
        <p>We applied the matrix method to the honeycomb lattice and obtained
        its exact solution and the triangular-net dual.</p>
        <p>The Curie point occurs at ch 2H = 2 in the honeycomb lattice and at
        exp(4H) = 3 in the triangular net.</p>
      </section>
      <p hidden>hidden-attribute-sentinel</p>
      <p aria-hidden="true">aria-hidden-sentinel</p>
      <p style="display:none">inline-style-hidden-sentinel</p>
      <noscript>noscript-hidden-sentinel</noscript>
      <template>template-hidden-sentinel</template>
    </article>
  </body>
</html>
"""
OUP_MINIMAL_DIV_HTML = b"""<!doctype html>
<html lang="en">
  <head><title></title><style>.article-content { display: block }</style></head>
  <body>
    <div class="minimal-article-container">
      <div class="article-header">
        <h1>The Statistics of Honeycomb and Triangular Lattice. I</h1>
        <p>Kodi Husimi and Itiro Sy&#244;zi</p>
        <p>https://doi.org/10.1143/ptp.5.2.177</p>
      </div>
      <div class="article-content">
        <h2>Summary</h2>
        <section class="abstract">
          <p>The Curie point occurs at ch 2H = 2 in the honeycomb lattice and
          at exp (4H) = 3 in the triangular net.</p>
        </section>
      </div>
    </div>
  </body>
</html>
"""


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


def _registry_routes_by_identity():
    identities = {
        canonical_source_identity(entry["source_url"])
        for entry in LITERATURE_STANDARD_RESULTS
    }
    return {
        identity: authoritative_route_for_identity(
            dict(zip(("kind", "value"), identity.split(":", 1)))
        )
        for identity in identities
    }


def test_final_authoritative_route_distribution_covers_exact_registry_sources():
    routes = _registry_routes_by_identity()

    assert len(routes) == 137
    assert Counter(route["kind"] for route in routes.values()) == {
        "aps_harvest_pdf": 78,
        "arxiv_export_pdf": 26,
        "arxiv_author_manuscript_pdf": 10,
        "nature_open_article_pdf": 5,
        "iop_article_pdf": 3,
        "nature_article_pdf": 2,
        "elsevier_article_api_xml": 2,
        "institutional_repository_pdf": 2,
        "science_article_pdf": 2,
        "acs_article_pdf": 1,
        "aip_article_discovery": 1,
        "author_repository_pdf": 1,
        "epl_iop_article_pdf": 1,
        "jpsj_article_pdf": 1,
        "oup_minimal_html": 1,
        "springer_content_pdf": 1,
    }
    assert Counter(route["expected_media_type"] for route in routes.values()) == {
        "application/pdf": 134,
        "application/xml": 2,
        "text/html": 1,
    }
    assert Counter(route["access_mode"] for route in routes.values()) == {
        "unattended": 123,
        "challenge_or_institutional": 9,
        "authenticated_session": 3,
        "api_key_or_entitlement": 2,
    }
    assert all(route["kind"] != "doi_content_negotiation" for route in routes.values())


@pytest.mark.parametrize(
    ("identity", "expected"),
    [
        (
            "doi:10.1143/ptp.5.2.177",
            {
                "kind": "oup_minimal_html",
                "url": "https://oup.silverchair-cdn.com/article-minimal/1942776",
                "expected_media_type": "text/html",
                "access_mode": "unattended",
                "artifact_identifier": "doi:10.1143/ptp.5.2.177",
                "work_identity_evidence": {
                    "kind": "canonical_identity",
                    "url": "https://doi.org/10.1143/ptp.5.2.177",
                },
            },
        ),
        (
            "doi:10.1088/0305-4470/17/13/020",
            {
                "kind": "institutional_repository_pdf",
                "url": "https://files01.core.ac.uk/download/pdf/572184419.pdf",
                "expected_media_type": "application/pdf",
                "access_mode": "unattended",
                "artifact_identifier": "core:572184419",
                "work_identity_evidence": {
                    "kind": "core_same_work_output",
                    "url": "https://api.core.ac.uk/v3/outputs/572184419",
                },
            },
        ),
        (
            "doi:10.1088/0305-4470/16/10/023",
            {
                "kind": "author_repository_pdf",
                "url": "https://www.lptmc.jussieu.fr/files/maillard/PUB2/Frustrated_jav16i10p2257.pdf",
                "expected_media_type": "application/pdf",
                "access_mode": "unattended",
                "artifact_identifier": "author-repository:Frustrated_jav16i10p2257.pdf",
                "work_identity_evidence": {
                    "kind": "author_publications_same_work",
                    "url": "https://www.lptmc.jussieu.fr/users/maillard",
                },
            },
        ),
        (
            "doi:10.1038/s41535-026-00868-6",
            {
                "kind": "nature_open_article_pdf",
                "url": "https://www.nature.com/articles/s41535-026-00868-6.pdf",
                "expected_media_type": "application/pdf",
                "access_mode": "unattended",
                "artifact_identifier": "doi:10.1038/s41535-026-00868-6",
                "work_identity_evidence": {
                    "kind": "canonical_identity",
                    "url": "https://doi.org/10.1038/s41535-026-00868-6",
                },
            },
        ),
    ],
)
def test_final_special_authoritative_routes_are_exact(identity, expected):
    kind, value = identity.split(":", 1)
    assert authoritative_route_for_identity({"kind": kind, "value": value}) == expected


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


CORE_MG_BIBLIOGRAPHIC_METADATA = {
    "doi": "10.1088/0305-4470/17/13/020",
    "title": "The Majumdar-Ghosh chain. Twofold ground state and elementary excitations",
    "authors": ["W. J. Caspers", "K. M. Emmett", "W. Magnus"],
}


def _core_mg_work_identity_document():
    return {
        "id": 572184419,
        "doi": "10.1088/0305-4470/17/13/020",
        "title": "The Majumdar-Ghosh chain. Twofold ground state and elementary excitations",
        "authors": [
            {"name": "W J Caspers"},
            {"name": "K M Emmett"},
            {"name": "W Magnus"},
        ],
        "downloadUrl": "https://files01.core.ac.uk/download/pdf/572184419.pdf",
    }


def _core_mg_route():
    return authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1088/0305-4470/17/13/020"}
    )


def test_core_same_work_output_binds_exact_doi_output_title_authors_and_pdf():
    validate_work_identity_document(
        _core_mg_work_identity_document(),
        identity={"kind": "doi", "value": "10.1088/0305-4470/17/13/020"},
        authoritative_route=_core_mg_route(),
        evidence_kind="core_same_work_output",
        bibliographic_metadata=CORE_MG_BIBLIOGRAPHIC_METADATA,
    )


@pytest.mark.parametrize(
    "perturbation",
    ("doi", "output_id", "title", "authors", "pdf_location"),
)
def test_core_same_work_output_rejects_each_independent_mismatch(perturbation):
    document = _core_mg_work_identity_document()
    if perturbation == "doi":
        document["doi"] = "10.1088/0305-4470/17/13/999"
    elif perturbation == "output_id":
        document["id"] = 572184418
    elif perturbation == "title":
        document["title"] = "A different spin-chain paper"
    elif perturbation == "authors":
        document["authors"][-1] = {"name": "A Different Author"}
    else:
        document["downloadUrl"] = "https://files01.core.ac.uk/download/pdf/572184418.pdf"

    with pytest.raises(SourceEvidenceError, match="work identity"):
        validate_work_identity_document(
            document,
            identity={"kind": "doi", "value": "10.1088/0305-4470/17/13/020"},
            authoritative_route=_core_mg_route(),
            evidence_kind="core_same_work_output",
            bibliographic_metadata=CORE_MG_BIBLIOGRAPHIC_METADATA,
        )


AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA = {
    "doi": "10.1088/0305-4470/16/10/023",
    "title": "Study of a two-dimensional fully frustrated model",
    "authors": ["T. Garel", "J. M. Maillard"],
}
AUTHOR_GAREL_PAGE = b"""<!doctype html>
<html><body><main>
  <h1>Publications</h1>
  <article>
    <p>Study of a two-dimensional fully frustrated model</p>
    <p>T Garel and J M Maillard</p>
    <p>https://doi.org/10.1088/0305-4470/16/10/023</p>
    <a href="../../files/maillard/PUB2/Frustrated_jav16i10p2257.pdf">article PDF</a>
  </article>
</main></body></html>
"""
AUTHOR_GAREL_DOI = b"10.1088/0305-4470/16/10/023"
AUTHOR_GAREL_RESOLVER = b"https://doi.org/" + AUTHOR_GAREL_DOI
EXTRA_DOI = b"10.9999/other"
ROUND5_HIDDEN_ZERO_AND_FUNCTION_STYLES = (
    pytest.param(b"opacity:0%", id="opacity-zero-percent"),
    pytest.param(b"opacity:+0", id="opacity-positive-zero"),
    pytest.param(b"opacity:-0", id="opacity-negative-zero"),
    pytest.param(b"opacity:+.0", id="opacity-positive-decimal-zero"),
    pytest.param(b"opacity:-0.0", id="opacity-negative-decimal-zero"),
    pytest.param(b"opacity:0e0", id="opacity-zero-exponent"),
    pytest.param(b"opacity:-0E+7", id="opacity-signed-zero-exponent"),
    pytest.param(b"font-size:0%", id="font-zero-percent"),
    pytest.param(b"font-size:+0", id="font-positive-unitless-zero"),
    pytest.param(b"font-size:-.0px", id="font-negative-decimal-zero-length"),
    pytest.param(b"font-size:0e0em", id="font-zero-exponent-length"),
    pytest.param(b"opacity:calc(0)", id="opacity-calc-zero"),
    pytest.param(b"font-size:calc(0px)", id="font-calc-zero-length"),
    pytest.param(b"display:var(--display)", id="display-ambiguous-function"),
    pytest.param(
        b"visibility:var(--visibility)",
        id="visibility-ambiguous-function",
    ),
    pytest.param(b"opacity:var(--opacity)", id="opacity-ambiguous-function"),
    pytest.param(b"font-size:var(--size)", id="font-ambiguous-function"),
    pytest.param(
        b"content-visibility:var(--content-visibility)",
        id="content-visibility-ambiguous-function",
    ),
    pytest.param(b"opacity:min(1, 1)", id="opacity-other-ambiguous-function"),
)
ROUND5_VISIBLE_STYLE_CONTROLS = (
    pytest.param(b"opacity:1", id="opacity-one"),
    pytest.param(b"opacity:0.1", id="opacity-adjacent-nonzero"),
    pytest.param(b"opacity:1e-9", id="opacity-nonzero-exponent"),
    pytest.param(b"font-size:1px", id="font-positive-length"),
    pytest.param(b"font-size:0.1px", id="font-adjacent-nonzero"),
    pytest.param(b"font-size:1e-9em", id="font-nonzero-exponent"),
    pytest.param(b"display:block", id="display-block"),
    pytest.param(b"visibility:visible", id="visibility-visible"),
    pytest.param(
        b"content-visibility:visible",
        id="content-visibility-visible",
    ),
    pytest.param(b"opacity:calc(1)", id="opacity-calc-one"),
    pytest.param(b"font-size:calc(1px)", id="font-calc-positive-length"),
)
ROUND5_COMMENT_HIDDEN_STYLES = (
    pytest.param(b"display/**/:none", id="comment-before-colon"),
    pytest.param(b"display:/**/none", id="comment-before-value"),
    pytest.param(
        b"display:none/**/ ! important",
        id="comment-before-important",
    ),
    pytest.param(b"opacity:/**/0", id="comment-before-opacity-zero"),
    pytest.param(b"font-size:/**/0", id="comment-before-font-zero"),
)
ROUND5_STATEMENT_AT_RULES = (
    pytest.param(b"@layer foo;", id="layer"),
    pytest.param(
        b'@import url("theme;v1.css") /* import; comment */;',
        id="import-with-quoted-semicolon-parens-comment",
    ),
    pytest.param(b'@charset "UTF-8";', id="charset-with-quoted-string"),
)
ROUND5_UNSUPPORTED_PREFIX_RULES = (
    pytest.param(
        b".complex > .unused { display:none }",
        id="complex-selector",
    ),
    pytest.param(
        b".escaped\\2d selector { display:none }",
        id="escaped-selector",
    ),
)
ROUND6_CLAMPED_OPACITY_STYLES = (
    pytest.param(b"opacity:-1", id="negative-integer"),
    pytest.param(b"opacity:-0.1", id="negative-decimal"),
    pytest.param(b"opacity:-1%", id="negative-percent"),
    pytest.param(b"opacity:-1e-9", id="negative-small-exponent"),
    pytest.param(b"opacity:-1e+2%", id="negative-large-percent"),
    pytest.param(b"opacity:calc(-1)", id="calc-negative-integer"),
    pytest.param(b"opacity:calc(-.1)", id="calc-negative-decimal"),
    pytest.param(b"opacity:calc(-1%)", id="calc-negative-percent"),
    pytest.param(
        b"opacity:calc(-1e-9)",
        id="calc-negative-exponent",
    ),
)
ROUND6_UNRELIABLE_NUMERIC_STYLES = (
    pytest.param(b"opacity:1e-9999", id="opacity-small-exponent"),
    pytest.param(
        b"opacity:1e-9999%",
        id="opacity-small-percent-exponent",
    ),
    pytest.param(
        b"font-size:1e-9999px",
        id="font-small-exponent",
    ),
    pytest.param(b"opacity:1e9999", id="opacity-large-exponent"),
    pytest.param(
        b"opacity:1e9999%",
        id="opacity-large-percent-exponent",
    ),
    pytest.param(
        b"font-size:1e9999px",
        id="font-large-exponent",
    ),
    pytest.param(
        b"opacity:calc(1e-9999)",
        id="opacity-calc-small-exponent",
    ),
    pytest.param(
        b"opacity:calc(1e9999%)",
        id="opacity-calc-large-percent-exponent",
    ),
    pytest.param(
        b"font-size:calc(1e-9999px)",
        id="font-calc-small-exponent",
    ),
    pytest.param(
        b"opacity:1e-00009999",
        id="opacity-leading-zero-exponent",
    ),
    pytest.param(
        b"opacity:1e999999999999999999999999999999999999",
        id="opacity-bounded-exponent-parser",
    ),
)
ROUND6_I1_HIDDEN_STYLES = (
    ROUND6_CLAMPED_OPACITY_STYLES + ROUND6_UNRELIABLE_NUMERIC_STYLES
)
ROUND6_I1_STYLESHEET_CASES = (
    pytest.param("class", b"opacity:-1", id="class-negative-integer"),
    pytest.param("id", b"opacity:-0.1", id="id-negative-decimal"),
    pytest.param("tag", b"opacity:-1%", id="tag-negative-percent"),
    pytest.param("class", b"opacity:calc(-1)", id="class-calc-negative"),
    pytest.param("id", b"opacity:calc(-.1)", id="id-calc-negative-decimal"),
    pytest.param("tag", b"opacity:calc(-1%)", id="tag-calc-negative-percent"),
    pytest.param(
        "class",
        b"opacity:1e-9999",
        id="class-small-exponent",
    ),
    pytest.param(
        "id",
        b"opacity:1e-9999%",
        id="id-small-percent-exponent",
    ),
    pytest.param(
        "tag",
        b"font-size:1e-9999px",
        id="tag-font-small-exponent",
    ),
    pytest.param(
        "class",
        b"opacity:1e9999",
        id="class-large-exponent",
    ),
    pytest.param(
        "id",
        b"opacity:1e9999%",
        id="id-large-percent-exponent",
    ),
    pytest.param(
        "tag",
        b"font-size:1e9999px",
        id="tag-font-large-exponent",
    ),
    pytest.param(
        "class",
        b"opacity:calc(1e-9999)",
        id="class-calc-small-exponent",
    ),
    pytest.param(
        "id",
        b"opacity:calc(1e9999%)",
        id="id-calc-large-percent-exponent",
    ),
    pytest.param(
        "tag",
        b"font-size:calc(1e-9999px)",
        id="tag-font-calc-small-exponent",
    ),
)
ROUND6_I1_VISIBLE_STYLES = (
    pytest.param(b"opacity:2", id="positive-clamps-to-one"),
    pytest.param(b"opacity:200%", id="positive-percent-clamps-to-one"),
    pytest.param(b"opacity:calc(2)", id="calc-positive-clamps-to-one"),
    pytest.param(
        b"opacity:calc(200%)",
        id="calc-positive-percent-clamps-to-one",
    ),
    pytest.param(b"opacity:1e-308", id="reliable-small-opacity"),
    pytest.param(b"opacity:1e308", id="reliable-large-opacity"),
    pytest.param(b"font-size:1e-308px", id="reliable-small-font"),
    pytest.param(b"font-size:1e308px", id="reliable-large-font"),
    pytest.param(b"font-size:-1px", id="negative-font-is-not-zero"),
    pytest.param(
        b"font-size:calc(-1px)",
        id="calc-negative-font-is-not-zero",
    ),
)
ROUND6_I1_VISIBLE_STYLESHEET_CASES = (
    pytest.param("class", b"opacity:2", id="class-positive-opacity"),
    pytest.param("id", b"opacity:200%", id="id-positive-percent"),
    pytest.param("tag", b"opacity:calc(2)", id="tag-calc-positive"),
    pytest.param(
        "class",
        b"opacity:1e-308",
        id="class-reliable-small-opacity",
    ),
    pytest.param(
        "id",
        b"font-size:1e308px",
        id="id-reliable-large-font",
    ),
    pytest.param(
        "tag",
        b"font-size:-1px",
        id="tag-negative-font-control",
    ),
)
ROUND6_COLLAPSED_VISIBILITY_STYLES = (
    pytest.param(b"visibility:collapse", id="collapse"),
    pytest.param(b"VISIBILITY:COLLAPSE", id="case-insensitive-collapse"),
    pytest.param(
        b"visibility: collapse !important",
        id="collapse-important",
    ),
)
ROUND6_VISIBLE_VISIBILITY_STYLES = (
    pytest.param(b"visibility:visible", id="visible"),
    pytest.param(b"visibility:inherit", id="inherit"),
    pytest.param(b"visibility:initial", id="initial"),
    pytest.param(
        b"VISIBILITY:VISIBLE !IMPORTANT",
        id="case-insensitive-visible-important",
    ),
)


def _author_garel_page_with_doi():
    if AUTHOR_GAREL_DOI in AUTHOR_GAREL_PAGE:
        return AUTHOR_GAREL_PAGE
    return AUTHOR_GAREL_PAGE.replace(
        b"    <a href=",
        b"    <p>https://doi.org/" + AUTHOR_GAREL_DOI + b"</p>\n    <a href=",
    )


def _author_garel_route():
    return authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1088/0305-4470/16/10/023"}
    )


def _validate_author_garel_page(page):
    return validate_work_identity_document(
        page,
        identity={"kind": "doi", "value": AUTHOR_GAREL_DOI.decode("ascii")},
        authoritative_route=_author_garel_route(),
        evidence_kind="author_publications_same_work",
        bibliographic_metadata=AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA,
    )


def _author_page_with_markup_before_pdf(markup):
    marker = (
        b'    <a href="../../files/maillard/PUB2/'
        b'Frustrated_jav16i10p2257.pdf">article PDF</a>'
    )
    assert marker in AUTHOR_GAREL_PAGE
    page = AUTHOR_GAREL_PAGE.replace(
        marker,
        b"    " + markup + b"\n" + marker,
        1,
    )
    assert page != AUTHOR_GAREL_PAGE
    return page


def _author_page_with_inline_doi_style(style, *, extra_doi):
    if extra_doi:
        return _author_page_with_markup_before_pdf(
            b'<p style="' + style + b'">' + EXTRA_DOI + b"</p>"
        )
    page = AUTHOR_GAREL_PAGE.replace(
        b"    <p>" + AUTHOR_GAREL_RESOLVER + b"</p>",
        b'    <p style="' + style + b'">' + AUTHOR_GAREL_RESOLVER + b"</p>",
        1,
    )
    assert page != AUTHOR_GAREL_PAGE
    return page


def _author_page_with_local_stylesheet(stylesheet, *, extra_doi):
    if extra_doi:
        page = _author_page_with_markup_before_pdf(
            b'<p class="hide-doi">' + EXTRA_DOI + b"</p>"
        )
    else:
        page = AUTHOR_GAREL_PAGE.replace(
            b"    <p>" + AUTHOR_GAREL_RESOLVER + b"</p>",
            b'    <p class="hide-doi">' + AUTHOR_GAREL_RESOLVER + b"</p>",
            1,
        )
    page = page.replace(
        b"</body>",
        b"<style>" + stylesheet + b"</style></body>",
        1,
    )
    assert page != AUTHOR_GAREL_PAGE
    return page


def _author_page_with_stylesheet_doi_style(
    style,
    *,
    selector_kind,
    extra_doi,
):
    selector = {
        "class": b".hide-doi",
        "id": b"#hide-doi",
        "tag": b"aside",
    }[selector_kind]
    page = _author_page_with_local_stylesheet(
        selector + b" { " + style + b" }",
        extra_doi=extra_doi,
    )
    value = EXTRA_DOI if extra_doi else AUTHOR_GAREL_RESOLVER
    if selector_kind == "id":
        page = page.replace(
            b'<p class="hide-doi">' + value + b"</p>",
            b'<p id="hide-doi">' + value + b"</p>",
            1,
        )
    elif selector_kind == "tag":
        page = page.replace(
            b'<p class="hide-doi">' + value + b"</p>",
            b"<aside>" + value + b"</aside>",
            1,
        )
    return page


def test_author_publications_same_work_binds_page_pdf_and_doi_metadata():
    validate_work_identity_document(
        AUTHOR_GAREL_PAGE,
        identity={"kind": "doi", "value": "10.1088/0305-4470/16/10/023"},
        authoritative_route=_author_garel_route(),
        evidence_kind="author_publications_same_work",
        bibliographic_metadata=AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA,
    )


@pytest.mark.parametrize("mutation", ("missing", "altered"))
def test_author_publications_same_work_requires_page_doi(mutation):
    page = _author_garel_page_with_doi()
    replacement = b"" if mutation == "missing" else b"10.1088/0305-4470/16/10/999"
    page = page.replace(AUTHOR_GAREL_DOI, replacement)
    with pytest.raises(SourceEvidenceError, match="DOI"):
        validate_work_identity_document(
            page,
            identity={"kind": "doi", "value": "10.1088/0305-4470/16/10/023"},
            authoritative_route=_author_garel_route(),
            evidence_kind="author_publications_same_work",
            bibliographic_metadata=AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA,
        )


@pytest.mark.parametrize("suffix", (b".999", b"/999", b"-other", b"_other"))
def test_author_publications_same_work_rejects_longer_doi_with_canonical_prefix(
    suffix,
):
    page = AUTHOR_GAREL_PAGE.replace(
        AUTHOR_GAREL_DOI,
        AUTHOR_GAREL_DOI + suffix,
    )
    with pytest.raises(SourceEvidenceError, match="DOI"):
        validate_work_identity_document(
            page,
            identity={"kind": "doi", "value": "10.1088/0305-4470/16/10/023"},
            authoritative_route=_author_garel_route(),
            evidence_kind="author_publications_same_work",
            bibliographic_metadata=AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA,
        )


@pytest.mark.parametrize(
    "fake_resolver",
    (
        b"evilhttps://doi.org/" + AUTHOR_GAREL_DOI,
        b"https://evil.invalid/https://doi.org/" + AUTHOR_GAREL_DOI,
    ),
    ids=("prefixed", "nested"),
)
@pytest.mark.parametrize(
    "carrier_kind",
    ("visible-text", "href", "citation-doi", "data-doi"),
)
def test_structured_doi_author_rejects_fake_resolver_carrier(
    carrier_kind,
    fake_resolver,
):
    if carrier_kind == "visible-text":
        page = AUTHOR_GAREL_PAGE.replace(
            AUTHOR_GAREL_RESOLVER,
            fake_resolver,
            1,
        )
    elif carrier_kind == "href":
        page = _author_page_with_markup_before_pdf(
            b'<a href="' + fake_resolver + b'">identity DOI</a>'
        )
    elif carrier_kind == "citation-doi":
        page = _author_page_with_markup_before_pdf(
            b'<meta name="citation_doi" content="' + fake_resolver + b'">'
        )
    else:
        page = AUTHOR_GAREL_PAGE.replace(
            b"  <article>",
            b'  <article data-doi="' + fake_resolver + b'">',
            1,
        )
    assert page != AUTHOR_GAREL_PAGE
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize(
    "invalid_href",
    (
        b"http://doi.org/" + AUTHOR_GAREL_DOI,
        b"https://user:password@doi.org/" + AUTHOR_GAREL_DOI,
        b"https://evil.invalid/" + AUTHOR_GAREL_DOI,
        b"https://doi.org:444/" + AUTHOR_GAREL_DOI,
        b"https://doi.org/" + AUTHOR_GAREL_DOI + b"?download=1",
        b"https://doi.org/" + AUTHOR_GAREL_DOI + b"#fragment",
    ),
    ids=("http", "userinfo", "wrong-host", "wrong-port", "query", "fragment"),
)
def test_structured_doi_author_rejects_invalid_resolver_href(invalid_href):
    page = _author_page_with_markup_before_pdf(
        b'<a href="' + invalid_href + b'">identity DOI</a>'
    )
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize("carrier_kind", ("href", "citation-doi", "data-doi"))
@pytest.mark.parametrize(
    "malformed_resolver",
    (
        AUTHOR_GAREL_RESOLVER + b";",
        AUTHOR_GAREL_RESOLVER + b"?",
        AUTHOR_GAREL_RESOLVER + b"#",
        AUTHOR_GAREL_RESOLVER + b";?",
        AUTHOR_GAREL_RESOLVER + b";#",
        b"https://doi.org:/" + AUTHOR_GAREL_DOI,
    ),
    ids=(
        "path-semicolon",
        "empty-query",
        "empty-fragment",
        "semicolon-empty-query",
        "semicolon-empty-fragment",
        "empty-port",
    ),
)
def test_structured_doi_author_rejects_raw_resolver_syntax_edges(
    carrier_kind,
    malformed_resolver,
):
    if carrier_kind == "href":
        page = _author_page_with_markup_before_pdf(
            b'<a href="' + malformed_resolver + b'">identity DOI</a>'
        )
    elif carrier_kind == "citation-doi":
        page = _author_page_with_markup_before_pdf(
            b'<meta name="citation_doi" content="'
            + malformed_resolver
            + b'">'
        )
    else:
        page = AUTHOR_GAREL_PAGE.replace(
            b"  <article>",
            b'  <article data-doi="' + malformed_resolver + b'">',
            1,
        )
    assert page != AUTHOR_GAREL_PAGE
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_author_garel_page(page)


def test_structured_doi_author_rejects_visible_resolver_with_empty_port():
    page = AUTHOR_GAREL_PAGE.replace(
        AUTHOR_GAREL_RESOLVER,
        b"https://doi.org:/" + AUTHOR_GAREL_DOI,
        1,
    )
    assert page != AUTHOR_GAREL_PAGE
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize(
    "valid_href",
    (
        b"https://doi.org/" + AUTHOR_GAREL_DOI,
        b"HTTPS://DOI.ORG:443/" + AUTHOR_GAREL_DOI.upper(),
    ),
    ids=("canonical", "normalized-default-port"),
)
def test_structured_doi_author_accepts_exact_resolver_href(valid_href):
    page = _author_page_with_markup_before_pdf(
        b'<a href="' + valid_href + b'">identity DOI</a>'
    )
    _validate_author_garel_page(page)


@pytest.mark.parametrize("attribute_kind", ("citation-doi", "data-doi"))
@pytest.mark.parametrize(
    "invalid_value",
    (
        b"Related " + AUTHOR_GAREL_DOI,
        b"DOI: " + AUTHOR_GAREL_DOI + b" verified",
    ),
    ids=("embedded-plain", "label-with-trailing-text"),
)
def test_structured_doi_author_rejects_nonwhole_metadata_value(
    attribute_kind,
    invalid_value,
):
    if attribute_kind == "citation-doi":
        page = _author_page_with_markup_before_pdf(
            b'<meta name="citation_doi" content="' + invalid_value + b'">'
        )
    else:
        page = AUTHOR_GAREL_PAGE.replace(
            b"  <article>",
            b'  <article data-doi="' + invalid_value + b'">',
            1,
        )
    assert page != AUTHOR_GAREL_PAGE
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize(
    "metadata_value",
    (
        AUTHOR_GAREL_DOI,
        b"DOI: " + AUTHOR_GAREL_DOI.upper(),
        b"HTTPS://DOI.ORG:443/" + AUTHOR_GAREL_DOI,
    ),
    ids=("plain", "labelled", "resolver"),
)
def test_structured_doi_author_accepts_whole_metadata_value(metadata_value):
    page = _author_page_with_markup_before_pdf(
        b'<meta name="citation_doi" content="' + metadata_value + b'">'
    )
    _validate_author_garel_page(page)


def test_structured_doi_author_accepts_duplicate_canonical_mixed_carriers():
    page = AUTHOR_GAREL_PAGE.replace(
        b"  <article>",
        b'  <article data-doi="DOI: ' + AUTHOR_GAREL_DOI + b'">',
        1,
    )
    marker = b"    <p>" + AUTHOR_GAREL_RESOLVER + b"</p>"
    page = page.replace(
        marker,
        marker
        + b'\n    <meta name="citation_doi" content="'
        + AUTHOR_GAREL_DOI.upper()
        + b'">',
        1,
    )
    assert page != AUTHOR_GAREL_PAGE
    _validate_author_garel_page(page)


def test_structured_doi_author_rejects_embedded_extra_bare_doi():
    page = _author_page_with_markup_before_pdf(
        b"<p>Related work " + EXTRA_DOI + b"</p>"
    )
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize(
    "presentation",
    (
        b"https://doi.org/10.1088/0305-4470/16/10/02<span>3</span>",
        AUTHOR_GAREL_DOI,
        b"DOI: " + AUTHOR_GAREL_DOI + b".",
        b"DOI: " + AUTHOR_GAREL_DOI + b", verified",
        b"(DOI: " + AUTHOR_GAREL_DOI + b")",
    ),
    ids=("inline-split", "standalone", "terminal-period", "comma-text", "parenthesized"),
)
def test_structured_doi_author_accepts_legal_visible_presentation(presentation):
    page = AUTHOR_GAREL_PAGE.replace(
        AUTHOR_GAREL_RESOLVER,
        presentation,
        1,
    )
    assert page != AUTHOR_GAREL_PAGE
    _validate_author_garel_page(page)


@pytest.mark.parametrize(
    "presentation",
    (
        b"(DOI: " + AUTHOR_GAREL_DOI + b").",
        b"(" + AUTHOR_GAREL_RESOLVER + b").",
        b"See (" + AUTHOR_GAREL_DOI + b").",
    ),
    ids=("parenthesized-label-period", "parenthesized-resolver-period", "prose-period"),
)
def test_structured_doi_author_accepts_iteratively_trimmed_presentation(
    presentation,
):
    page = AUTHOR_GAREL_PAGE.replace(AUTHOR_GAREL_RESOLVER, presentation, 1)
    assert page != AUTHOR_GAREL_PAGE
    _validate_author_garel_page(page)


@pytest.mark.parametrize(
    "surplus_presentation",
    (
        AUTHOR_GAREL_DOI + b"..",
        AUTHOR_GAREL_DOI + b",,",
        AUTHOR_GAREL_DOI + b".,",
        AUTHOR_GAREL_DOI + b",.",
        AUTHOR_GAREL_RESOLVER + b"..",
        AUTHOR_GAREL_RESOLVER + b",,",
        AUTHOR_GAREL_RESOLVER + b".,",
        AUTHOR_GAREL_RESOLVER + b",.",
        b"(DOI: " + AUTHOR_GAREL_DOI + b")..",
        b"(" + AUTHOR_GAREL_RESOLVER + b")..",
        b"See (" + AUTHOR_GAREL_DOI + b").,",
        b"((" + AUTHOR_GAREL_RESOLVER + b")).",
    ),
    ids=(
        "bare-double-period",
        "bare-double-comma",
        "bare-period-comma",
        "bare-comma-period",
        "resolver-double-period",
        "resolver-double-comma",
        "resolver-period-comma",
        "resolver-comma-period",
        "labelled-wrapper-double-period",
        "resolver-wrapper-double-period",
        "prose-wrapper-mixed-punctuation",
        "resolver-double-wrapper",
    ),
)
def test_structured_doi_author_rejects_surplus_presentation_punctuation(
    surplus_presentation,
):
    page = AUTHOR_GAREL_PAGE.replace(
        AUTHOR_GAREL_RESOLVER,
        surplus_presentation,
        1,
    )
    assert page != AUTHOR_GAREL_PAGE
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize(
    "presentation",
    (
        AUTHOR_GAREL_DOI + b".",
        AUTHOR_GAREL_DOI + b", verified",
        AUTHOR_GAREL_RESOLVER + b".",
        AUTHOR_GAREL_RESOLVER + b", verified",
        b"(" + AUTHOR_GAREL_DOI + b").",
    ),
    ids=(
        "bare-period",
        "bare-comma",
        "resolver-period",
        "resolver-comma",
        "bare-wrapper-period",
    ),
)
def test_structured_doi_author_accepts_single_presentation_layer(presentation):
    page = AUTHOR_GAREL_PAGE.replace(AUTHOR_GAREL_RESOLVER, presentation, 1)
    assert page != AUTHOR_GAREL_PAGE
    _validate_author_garel_page(page)


@pytest.mark.parametrize(
    "identifier",
    (
        "10.1234/example.999",
        "10.1234/example/999",
        "10.1234/example-other",
        "10.1234/example_other",
        "10.1234/example;",
        "10.1234/example(test)",
        "10.1234/example[part]{version}",
    ),
    ids=(
        "period-digits",
        "slash-digits",
        "hyphen-suffix",
        "underscore-suffix",
        "semicolon-suffix",
        "balanced-parentheses",
        "balanced-brackets-and-braces",
    ),
)
@pytest.mark.parametrize("carrier", ("plain", "resolver"))
def test_round5_visible_doi_normalization_preserves_identifier_content(
    identifier,
    carrier,
):
    rendered = (
        identifier
        if carrier == "plain"
        else f"https://doi.org/{identifier}"
    )
    values, valid_carriers = evidence_sources._visible_text_doi_values(
        (rendered,)
    )
    assert valid_carriers
    assert values == {identifier}


def test_round5_visible_doi_carriers_are_normalized_once(monkeypatch):
    calls = {"resolver": 0, "text": 0}
    original_resolver_normalizer = (
        evidence_sources._trim_visible_url_presentation
    )
    original_text_normalizer = evidence_sources._normalized_text_doi_value

    def count_resolver_normalization(token):
        calls["resolver"] += 1
        return original_resolver_normalizer(token)

    def count_text_normalization(text, match):
        calls["text"] += 1
        return original_text_normalizer(text, match)

    monkeypatch.setattr(
        evidence_sources,
        "_trim_visible_url_presentation",
        count_resolver_normalization,
    )
    monkeypatch.setattr(
        evidence_sources,
        "_normalized_text_doi_value",
        count_text_normalization,
    )
    values, valid_carriers = evidence_sources._visible_text_doi_values(
        (
            "(https://doi.org/10.1234/example). "
            "(DOI: 10.1234/example).",
        )
    )
    assert valid_carriers
    assert values == {"10.1234/example"}
    assert calls == {"resolver": 1, "text": 1}


@pytest.mark.parametrize(
    "prefix",
    (
        b"evil_",
        b"evil-",
        b"evil.",
        b"evil/",
        "é".encode("utf-8"),
        "汉".encode("utf-8"),
        b"evil(",
    ),
    ids=(
        "underscore",
        "hyphen",
        "period",
        "slash",
        "unicode-letter",
        "unicode-cjk",
        "opening-delimiter-without-boundary",
    ),
)
def test_structured_doi_author_rejects_bare_doi_after_identifier_continuation(
    prefix,
):
    suffix = b")" if prefix.endswith(b"(") else b""
    page = AUTHOR_GAREL_PAGE.replace(
        AUTHOR_GAREL_RESOLVER,
        prefix + AUTHOR_GAREL_DOI + suffix,
        1,
    )
    assert page != AUTHOR_GAREL_PAGE
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize(
    "style",
    (
        b"display:none ! important",
        b"visibility:hidden ! important",
        b"opacity:0",
        b"font-size:0",
        b"content-visibility:hidden",
    ),
    ids=(
        "display-important-whitespace",
        "visibility-important-whitespace",
        "zero-opacity",
        "zero-font-size",
        "hidden-content-visibility",
    ),
)
def test_structured_doi_author_rejects_inline_style_hidden_sole_doi(style):
    page = AUTHOR_GAREL_PAGE.replace(
        b"    <p>" + AUTHOR_GAREL_RESOLVER + b"</p>",
        b'    <p style="' + style + b'">' + AUTHOR_GAREL_RESOLVER + b"</p>",
        1,
    )
    assert page != AUTHOR_GAREL_PAGE
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize(
    "style",
    (
        b"display:none ! important",
        b"visibility:hidden ! important",
        b"opacity:0",
        b"font-size:0",
        b"content-visibility:hidden",
    ),
)
def test_structured_doi_author_ignores_inline_style_hidden_extra_doi(style):
    page = _author_page_with_markup_before_pdf(
        b'<p style="' + style + b'">' + EXTRA_DOI + b"</p>"
    )
    _validate_author_garel_page(page)


@pytest.mark.parametrize(
    ("selector", "doi_markup", "declaration"),
    (
        (b".hide-doi", b'<p class="hide-doi">', b"display:none"),
        (b"#hidden-doi", b'<p id="hidden-doi">', b"visibility:hidden"),
        (b"aside", b"<aside>", b"opacity:0"),
    ),
    ids=("class", "id", "tag"),
)
def test_structured_doi_author_stylesheet_hides_sole_doi_regardless_of_order(
    selector,
    doi_markup,
    declaration,
):
    closing_tag = b"</aside>" if doi_markup == b"<aside>" else b"</p>"
    page = AUTHOR_GAREL_PAGE.replace(
        b"    <p>" + AUTHOR_GAREL_RESOLVER + b"</p>",
        b"    " + doi_markup + AUTHOR_GAREL_RESOLVER + closing_tag,
        1,
    )
    page = page.replace(
        b"</body>",
        b"<style>" + selector + b" { " + declaration + b" }</style></body>",
        1,
    )
    assert page != AUTHOR_GAREL_PAGE
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_author_garel_page(page)


def test_structured_doi_author_stylesheet_hidden_extra_doi_does_not_pollute():
    page = _author_page_with_markup_before_pdf(
        b'<p class="hide-doi">' + EXTRA_DOI + b"</p>"
    )
    page = page.replace(
        b"</body>",
        b"<style>.hide-doi { display:none }</style></body>",
        1,
    )
    _validate_author_garel_page(page)


def test_structured_doi_author_ordinary_stylesheet_class_remains_visible():
    page = AUTHOR_GAREL_PAGE.replace(
        b"    <p>" + AUTHOR_GAREL_RESOLVER + b"</p>",
        b'    <p class="show-doi">' + AUTHOR_GAREL_RESOLVER + b"</p>",
        1,
    )
    page = page.replace(
        b"</body>",
        b"<style>.show-doi { color: red }</style></body>",
        1,
    )
    _validate_author_garel_page(page)


def test_author_stylesheet_prepass_fails_closed_above_character_bound(
    monkeypatch,
):
    monkeypatch.setattr(
        evidence_sources,
        "_MAX_LOCAL_STYLESHEET_CHARACTERS",
        1,
    )
    page = AUTHOR_GAREL_PAGE.replace(
        b"</body>",
        b"<style>.show-doi { color: red }</style></body>",
        1,
    )
    with pytest.raises(SourceEvidenceError, match="validation bound"):
        _validate_author_garel_page(page)


def test_round5_author_stylesheet_comments_count_before_character_bound(
    monkeypatch,
):
    monkeypatch.setattr(
        evidence_sources,
        "_MAX_LOCAL_STYLESHEET_CHARACTERS",
        16,
    )
    page = _author_page_with_local_stylesheet(
        b"/*" + (b"x" * 32) + b"*/ .hide-doi { opacity:1 }",
        extra_doi=False,
    )
    with pytest.raises(SourceEvidenceError, match="validation bound"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("style", ROUND5_HIDDEN_ZERO_AND_FUNCTION_STYLES)
def test_round5_author_zero_and_ambiguous_function_styles_hide_doi(
    style,
    extra_doi,
):
    page = _author_page_with_inline_doi_style(style, extra_doi=extra_doi)
    if extra_doi:
        _validate_author_garel_page(page)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize(
    ("selector_kind", "declaration"),
    (
        ("class", b"opacity:+0"),
        ("id", b"font-size:calc(0px)"),
        ("tag", b"display:var(--display)"),
    ),
    ids=("class-zero", "id-calc-zero", "tag-ambiguous-function"),
)
def test_round5_author_simple_stylesheet_selectors_apply_hidden_values(
    selector_kind,
    declaration,
    extra_doi,
):
    selector = {
        "class": b".hide-doi",
        "id": b"#hide-doi",
        "tag": b"aside",
    }[selector_kind]
    page = _author_page_with_local_stylesheet(
        selector + b" { " + declaration + b" }",
        extra_doi=extra_doi,
    )
    value = EXTRA_DOI if extra_doi else AUTHOR_GAREL_RESOLVER
    if selector_kind == "id":
        page = page.replace(
            b'<p class="hide-doi">' + value + b"</p>",
            b'<p id="hide-doi">' + value + b"</p>",
            1,
        )
    elif selector_kind == "tag":
        page = page.replace(
            b'<p class="hide-doi">' + value + b"</p>",
            b"<aside>" + value + b"</aside>",
            1,
        )
    if extra_doi:
        _validate_author_garel_page(page)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("style", ROUND5_VISIBLE_STYLE_CONTROLS)
def test_round5_author_nonzero_and_ordinary_styles_remain_visible(
    style,
    extra_doi,
):
    page = _author_page_with_inline_doi_style(style, extra_doi=extra_doi)
    if extra_doi:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)
    else:
        _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("style", ROUND6_I1_HIDDEN_STYLES)
def test_round6_i1_author_clamped_and_unreliable_inline_values_hide_doi(
    style,
    extra_doi,
):
    page = _author_page_with_inline_doi_style(style, extra_doi=extra_doi)
    if extra_doi:
        _validate_author_garel_page(page)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize(
    ("selector_kind", "style"),
    ROUND6_I1_STYLESHEET_CASES,
)
def test_round6_i1_author_clamped_and_unreliable_stylesheet_values_hide_doi(
    selector_kind,
    style,
    extra_doi,
):
    page = _author_page_with_stylesheet_doi_style(
        style,
        selector_kind=selector_kind,
        extra_doi=extra_doi,
    )
    if extra_doi:
        _validate_author_garel_page(page)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("style", ROUND6_I1_VISIBLE_STYLES)
def test_round6_i1_author_reliable_positive_and_negative_font_controls_visible(
    style,
    extra_doi,
):
    page = _author_page_with_inline_doi_style(style, extra_doi=extra_doi)
    if extra_doi:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)
    else:
        _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize(
    ("selector_kind", "style"),
    ROUND6_I1_VISIBLE_STYLESHEET_CASES,
)
def test_round6_i1_author_reliable_stylesheet_controls_remain_visible(
    selector_kind,
    style,
    extra_doi,
):
    page = _author_page_with_stylesheet_doi_style(
        style,
        selector_kind=selector_kind,
        extra_doi=extra_doi,
    )
    if extra_doi:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)
    else:
        _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("style", ROUND6_COLLAPSED_VISIBILITY_STYLES)
def test_round6_i2_author_collapsed_inline_visibility_hides_doi(
    style,
    extra_doi,
):
    page = _author_page_with_inline_doi_style(style, extra_doi=extra_doi)
    if extra_doi:
        _validate_author_garel_page(page)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("selector_kind", ("class", "id", "tag"))
@pytest.mark.parametrize("style", ROUND6_COLLAPSED_VISIBILITY_STYLES)
def test_round6_i2_author_collapsed_stylesheet_visibility_hides_doi(
    style,
    selector_kind,
    extra_doi,
):
    page = _author_page_with_stylesheet_doi_style(
        style,
        selector_kind=selector_kind,
        extra_doi=extra_doi,
    )
    if extra_doi:
        _validate_author_garel_page(page)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("style", ROUND6_VISIBLE_VISIBILITY_STYLES)
def test_round6_i2_author_ordinary_inline_visibility_remains_visible(
    style,
    extra_doi,
):
    page = _author_page_with_inline_doi_style(style, extra_doi=extra_doi)
    if extra_doi:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)
    else:
        _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize(
    ("selector_kind", "style"),
    (
        ("class", b"visibility:visible"),
        ("id", b"visibility:inherit"),
        ("tag", b"visibility:initial"),
    ),
    ids=("class-visible", "id-inherit", "tag-initial"),
)
def test_round6_i2_author_ordinary_stylesheet_visibility_remains_visible(
    selector_kind,
    style,
    extra_doi,
):
    page = _author_page_with_stylesheet_doi_style(
        style,
        selector_kind=selector_kind,
        extra_doi=extra_doi,
    )
    if extra_doi:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)
    else:
        _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("style", ROUND5_COMMENT_HIDDEN_STYLES)
def test_round5_author_inline_css_comments_preserve_hidden_declarations(
    style,
    extra_doi,
):
    page = _author_page_with_inline_doi_style(style, extra_doi=extra_doi)
    if extra_doi:
        _validate_author_garel_page(page)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
def test_round5_author_unterminated_inline_css_comment_hides_fail_closed(
    extra_doi,
):
    page = _author_page_with_inline_doi_style(
        b"display:/*unterminated",
        extra_doi=extra_doi,
    )
    if extra_doi:
        _validate_author_garel_page(page)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
def test_round5_author_overlimit_inline_css_hides_fail_closed(
    monkeypatch,
    extra_doi,
):
    monkeypatch.setattr(
        evidence_sources,
        "_MAX_INLINE_STYLE_CHARACTERS",
        8,
        raising=False,
    )
    page = _author_page_with_inline_doi_style(
        b"display:block;opacity:1",
        extra_doi=extra_doi,
    )
    if extra_doi:
        _validate_author_garel_page(page)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("at_rule", ROUND5_STATEMENT_AT_RULES)
def test_round5_author_statement_at_rule_does_not_swallow_hidden_rule(
    at_rule,
    extra_doi,
):
    stylesheet = at_rule + b"\n.hide-doi { display:none }"
    page = _author_page_with_local_stylesheet(stylesheet, extra_doi=extra_doi)
    if extra_doi:
        _validate_author_garel_page(page)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("unsupported_rule", ROUND5_UNSUPPORTED_PREFIX_RULES)
def test_round5_author_unsupported_selector_does_not_swallow_hidden_rule(
    unsupported_rule,
    extra_doi,
):
    stylesheet = unsupported_rule + b"\n.hide-doi { display:none }"
    page = _author_page_with_local_stylesheet(stylesheet, extra_doi=extra_doi)
    if extra_doi:
        _validate_author_garel_page(page)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
def test_round5_author_cdo_cdc_wrapper_preserves_hidden_rule(extra_doi):
    page = _author_page_with_local_stylesheet(
        b"<!--\n.hide-doi { display:none }\n-->",
        extra_doi=extra_doi,
    )
    if extra_doi:
        _validate_author_garel_page(page)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("at_rule", ROUND5_STATEMENT_AT_RULES)
def test_round5_author_statement_at_rule_preserves_visible_control(
    at_rule,
    extra_doi,
):
    stylesheet = at_rule + b"\n.hide-doi { opacity:1 }"
    page = _author_page_with_local_stylesheet(stylesheet, extra_doi=extra_doi)
    if extra_doi:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)
    else:
        _validate_author_garel_page(page)


@pytest.mark.parametrize(
    "ambiguous_stylesheet",
    (
        b"@media screen { .hide-doi { opacity:1 } }",
        b"orphan-token; .hide-doi { opacity:1 }",
        b"/* unterminated",
        b'@import url("unterminated); .hide-doi { display:none }',
    ),
    ids=(
        "unsupported-block-at-rule",
        "ambiguous-residual-statement",
        "unterminated-comment",
        "unterminated-at-rule-string-paren",
    ),
)
def test_round5_author_ambiguous_stylesheet_fails_closed(ambiguous_stylesheet):
    page = _author_page_with_local_stylesheet(
        ambiguous_stylesheet,
        extra_doi=False,
    )
    with pytest.raises(SourceEvidenceError, match="style|CSS|validation"):
        _validate_author_garel_page(page)


def test_round5_author_statement_at_rules_count_toward_stylesheet_bound(
    monkeypatch,
):
    monkeypatch.setattr(
        evidence_sources,
        "_MAX_LOCAL_STYLESHEET_RULES",
        1,
    )
    page = _author_page_with_local_stylesheet(
        b"@layer one; @layer two; .hide-doi { opacity:1 }",
        extra_doi=False,
    )
    with pytest.raises(SourceEvidenceError, match="too many"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize(
    "hidden_link",
    (
        b"<template><a href='../../files/maillard/PUB2/Frustrated_jav16i10p2257.pdf'>PDF</a></template>",
        b"<script><a href='../../files/maillard/PUB2/Frustrated_jav16i10p2257.pdf'>PDF</a></script>",
        b"<style><a href='../../files/maillard/PUB2/Frustrated_jav16i10p2257.pdf'>PDF</a></style>",
        b"<noscript><a href='../../files/maillard/PUB2/Frustrated_jav16i10p2257.pdf'>PDF</a></noscript>",
        b"<a hidden href='../../files/maillard/PUB2/Frustrated_jav16i10p2257.pdf'>PDF</a>",
        b"<a aria-hidden='true' href='../../files/maillard/PUB2/Frustrated_jav16i10p2257.pdf'>PDF</a>",
        b"<a style='display:none' href='../../files/maillard/PUB2/Frustrated_jav16i10p2257.pdf'>PDF</a>",
    ),
)
def test_author_publications_same_work_rejects_invisible_pdf_link(hidden_link):
    page = _author_garel_page_with_doi()
    page = re.sub(
        rb"<a href=\"\.\./\.\./files/maillard/PUB2/Frustrated_jav16i10p2257\.pdf\">article PDF</a>",
        hidden_link,
        page,
    )
    with pytest.raises(SourceEvidenceError, match="work identity|record|PDF"):
        validate_work_identity_document(
            page,
            identity={"kind": "doi", "value": "10.1088/0305-4470/16/10/023"},
            authoritative_route=_author_garel_route(),
            evidence_kind="author_publications_same_work",
            bibliographic_metadata=AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA,
        )


def test_author_publications_same_work_rejects_link_from_wrong_record():
    page = b"""<html><body><main>
      <article>
        <p>Study of a two-dimensional fully frustrated model</p>
        <p>T Garel and J M Maillard</p>
        <p>10.1088/0305-4470/16/10/023</p>
        <a href="../../files/maillard/PUB2/different.pdf">wrong PDF</a>
      </article>
      <article>
        <p>An unrelated publication by Other Authors</p>
        <p>10.0000/unrelated</p>
        <a href="../../files/maillard/PUB2/Frustrated_jav16i10p2257.pdf">other PDF</a>
      </article>
    </main></body></html>"""
    with pytest.raises(SourceEvidenceError, match="record"):
        validate_work_identity_document(
            page,
            identity={"kind": "doi", "value": "10.1088/0305-4470/16/10/023"},
            authoritative_route=_author_garel_route(),
            evidence_kind="author_publications_same_work",
            bibliographic_metadata=AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA,
        )


def test_author_publications_same_work_rejects_cross_record_splice():
    page = b"""<html><body><main>
      <article><p>Study of a two-dimensional fully frustrated model</p></article>
      <article><p>T Garel and J M Maillard</p></article>
      <article><p>10.1088/0305-4470/16/10/023</p></article>
      <article><a href="../../files/maillard/PUB2/Frustrated_jav16i10p2257.pdf">PDF</a></article>
    </main></body></html>"""
    with pytest.raises(SourceEvidenceError, match="record"):
        validate_work_identity_document(
            page,
            identity={"kind": "doi", "value": "10.1088/0305-4470/16/10/023"},
            authoritative_route=_author_garel_route(),
            evidence_kind="author_publications_same_work",
            bibliographic_metadata=AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA,
        )


@pytest.mark.parametrize(
    "perturbation",
    ("title", "author", "link_target", "doi_metadata", "base_url"),
)
def test_author_publications_same_work_rejects_each_independent_mismatch(perturbation):
    page = AUTHOR_GAREL_PAGE
    route = copy.deepcopy(_author_garel_route())
    metadata = dict(AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA)
    if perturbation == "title":
        page = page.replace(
            b"Study of a two-dimensional fully frustrated model",
            b"A different publication",
        )
    elif perturbation == "author":
        page = page.replace(b"J M Maillard", b"A Different Author")
    elif perturbation == "link_target":
        page = page.replace(
            b"Frustrated_jav16i10p2257.pdf",
            b"Different_jav16i10p2257.pdf",
        )
    elif perturbation == "doi_metadata":
        metadata["doi"] = "10.1088/0305-4470/16/10/999"
    else:
        route["work_identity_evidence"]["url"] = (
            "https://publications.example.invalid/users/maillard"
        )

    with pytest.raises(SourceEvidenceError, match="work identity"):
        validate_work_identity_document(
            page,
            identity={"kind": "doi", "value": "10.1088/0305-4470/16/10/023"},
            authoritative_route=route,
            evidence_kind="author_publications_same_work",
            bibliographic_metadata=metadata,
        )


def _special_sidecar_cache(tmp_path, evidence_kind):
    if evidence_kind == "core_same_work_output":
        route_spec = _core_mg_route()
        identity_value = "10.1088/0305-4470/17/13/020"
        metadata = CORE_MG_BIBLIOGRAPHIC_METADATA
        sidecar = json.dumps(
            _core_mg_work_identity_document(), sort_keys=True
        ).encode("utf-8")
        sidecar_name = "work-identity.json"
        sidecar_media_type = "application/json"
    else:
        route_spec = _author_garel_route()
        identity_value = "10.1088/0305-4470/16/10/023"
        metadata = AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA
        sidecar = AUTHOR_GAREL_PAGE
        sidecar_name = "work-identity.html"
        sidecar_media_type = "text/html"
    source_id = "doi_" + hashlib.sha256(
        f"doi:{identity_value}".encode("ascii")
    ).hexdigest()[:20]
    payload = _minimal_pdf("Locally verified special-route source payload.")
    source = {
        "source_id": source_id,
        "canonical_identity": {"kind": "doi", "value": identity_value},
        "canonical_url": f"https://doi.org/{identity_value}",
        "benchmark_names": ["fixture_benchmark"],
    }
    route = {
        "source_id": source_id,
        "authoritative_retrieval_route": route_spec,
        "expected_media_type": "application/pdf",
        "access_mode": "unattended",
    }
    descriptor = {
        "kind": evidence_kind,
        "url": route_spec["work_identity_evidence"]["url"],
        "media_type": sidecar_media_type,
        "payload_relative_path": sidecar_name,
        "payload_sha256": hashlib.sha256(sidecar).hexdigest(),
        "payload_byte_length": len(sidecar),
    }
    provenance = {
        "schema_version": 1,
        "source_id": source_id,
        "source_identity": {
            **source["canonical_identity"],
            "canonical_url": source["canonical_url"],
        },
        "bibliographic_metadata": {
            "title": metadata["title"],
            "authors": metadata["authors"],
            "venue": "Journal of Physics A",
            "publication_date": "1984-01-01" if "17/13" in identity_value else "1983-01-01",
        },
        "retrieval_metadata": {
            "url": route_spec["url"],
            "retrieved_at": "2026-07-31T12:00:00+08:00",
            "method": route_spec["kind"],
            "authoritative_origin": (
                "institutional_repository"
                if evidence_kind == "core_same_work_output"
                else "author_repository"
            ),
            "http_status": 200,
            "response_headers": {"content-type": "application/pdf"},
            "immutable_artifact_identifier": route_spec["artifact_identifier"],
            "work_identity_evidence": descriptor,
        },
        "media_type": "application/pdf",
        "raw_payload_sha256": hashlib.sha256(payload).hexdigest(),
        "raw_payload_byte_length": len(payload),
        "payload_relative_path": "source.pdf",
        "artifact_coordinates": {
            "kind": "whole_payload",
            "start_byte": 0,
            "end_byte": len(payload),
        },
        "license_access_notes": {
            "access_status": "open",
            "redistributability": "fixture_only",
            "notes": "Synthetic same-work cache fixture.",
        },
        "citation_metadata_verification": {
            "status": "verified",
            "verified_fields": ["title", "authors", "doi"],
        },
        "text_extraction": {
            "tool": "pdftotext",
            "version": _pdftotext_version(),
            "deterministic": True,
            "arguments": ["-layout", "-enc", "UTF-8"],
        },
    }
    source_dir = tmp_path / source_id
    source_dir.mkdir()
    source_dir.joinpath("source.pdf").write_bytes(payload)
    source_dir.joinpath(sidecar_name).write_bytes(sidecar)
    source_dir.joinpath("provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return source_dir, source, route, descriptor


@pytest.mark.parametrize(
    ("evidence_kind", "sidecar_name", "media_type"),
    [
        ("core_same_work_output", "work-identity.json", "application/json"),
        ("author_publications_same_work", "work-identity.html", "text/html"),
    ],
)
def test_loader_accepts_media_aware_hashed_same_work_sidecar(
    tmp_path, evidence_kind, sidecar_name, media_type
):
    source_dir, source, route, descriptor = _special_sidecar_cache(
        tmp_path, evidence_kind
    )
    verified = load_verified_source(
        source_dir,
        expected_source=source,
        provisioning_route=route,
    )
    assert verified.source_id == source["source_id"]
    assert descriptor["payload_relative_path"] == sidecar_name
    assert descriptor["media_type"] == media_type


@pytest.mark.parametrize(
    "evidence_kind", ("core_same_work_output", "author_publications_same_work")
)
def test_loader_hashes_raw_same_work_sidecar_before_parsing(tmp_path, evidence_kind):
    source_dir, source, route, descriptor = _special_sidecar_cache(
        tmp_path, evidence_kind
    )
    source_dir.joinpath(descriptor["payload_relative_path"]).write_bytes(b"{}")
    with pytest.raises(SourceEvidenceError, match="SHA-256"):
        load_verified_source(
            source_dir,
            expected_source=source,
            provisioning_route=route,
        )


class _FixtureHTTPResponse:
    def __init__(
        self,
        payload,
        *,
        content_type,
        final_url="https://sidecar.example.invalid/evidence",
    ):
        self._payload = payload
        self.status = 200
        self.headers = {"Content-Type": content_type}
        self._final_url = final_url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self._payload

    def geturl(self):
        return self._final_url


@pytest.mark.parametrize(
    ("evidence_kind", "payload", "metadata", "expected_name", "expected_media"),
    [
        (
            "core_same_work_output",
            json.dumps(_core_mg_work_identity_document(), sort_keys=True).encode("utf-8"),
            CORE_MG_BIBLIOGRAPHIC_METADATA,
            "work-identity.json",
            "application/json",
        ),
        (
            "author_publications_same_work",
            AUTHOR_GAREL_PAGE,
            AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA,
            "work-identity.html",
            "text/html",
        ),
    ],
)
def test_fetcher_preserves_raw_media_aware_same_work_sidecar(
    monkeypatch,
    evidence_kind,
    payload,
    metadata,
    expected_name,
    expected_media,
):
    route_spec = (
        _core_mg_route()
        if evidence_kind == "core_same_work_output"
        else _author_garel_route()
    )
    source = {
        "canonical_identity": {
            "kind": "doi",
            "value": metadata["doi"],
        }
    }
    route = {"authoritative_retrieval_route": route_spec}
    class FixtureOpener:
        def open(self, request, timeout):
            return _FixtureHTTPResponse(
                payload,
                content_type=expected_media,
                final_url=request.full_url,
            )

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )

    evidence = source_fetcher._fetch_work_identity_evidence(
        source,
        route,
        object(),
        bibliographic_metadata={key: value for key, value in metadata.items() if key != "doi"},
    )

    assert evidence["payload"] == payload
    assert evidence["descriptor"]["payload_relative_path"] == expected_name
    assert evidence["descriptor"]["media_type"] == expected_media
    assert evidence["descriptor"]["payload_sha256"] == hashlib.sha256(payload).hexdigest()
    assert evidence["descriptor"]["payload_byte_length"] == len(payload)


@pytest.mark.parametrize(
    ("evidence_kind", "raw_payload", "metadata", "expected_events"),
    [
        (
            "core_same_work_output",
            json.dumps(_core_mg_work_identity_document(), sort_keys=True).encode("utf-8"),
            CORE_MG_BIBLIOGRAPHIC_METADATA,
            ["sha256", "length", "json-parse", "validate"],
        ),
        (
            "author_publications_same_work",
            AUTHOR_GAREL_PAGE,
            AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA,
            ["sha256", "length", "validate", "html-parse"],
        ),
    ],
)
def test_fetcher_fingerprints_raw_sidecar_before_parse_or_validation(
    monkeypatch,
    evidence_kind,
    raw_payload,
    metadata,
    expected_events,
):
    events = []

    class TrackedPayload(bytes):
        def __len__(self):
            events.append("length")
            return super().__len__()

    payload = TrackedPayload(raw_payload)
    expected_sha256 = hashlib.sha256(raw_payload).hexdigest()
    real_sha256 = source_fetcher.hashlib.sha256
    real_json_loads = source_fetcher.json.loads
    real_validate = source_fetcher.validate_work_identity_document
    real_html_visible_text = evidence_sources._html_visible_text

    def tracked_sha256(value):
        assert value is payload
        events.append("sha256")
        return real_sha256(value)

    def tracked_json_loads(*args, **kwargs):
        events.append("json-parse")
        return real_json_loads(*args, **kwargs)

    def tracked_validate(*args, **kwargs):
        events.append("validate")
        return real_validate(*args, **kwargs)

    def tracked_html_visible_text(*args, **kwargs):
        events.append("html-parse")
        return real_html_visible_text(*args, **kwargs)

    route_spec = (
        _core_mg_route()
        if evidence_kind == "core_same_work_output"
        else _author_garel_route()
    )

    class FixtureOpener:
        def open(self, request, timeout):
            return _FixtureHTTPResponse(
                payload,
                content_type=(
                    "text/html"
                    if evidence_kind == "author_publications_same_work"
                    else "application/json"
                ),
                final_url=request.full_url,
            )

    monkeypatch.setattr(source_fetcher.hashlib, "sha256", tracked_sha256)
    monkeypatch.setattr(source_fetcher.json, "loads", tracked_json_loads)
    monkeypatch.setattr(
        source_fetcher,
        "validate_work_identity_document",
        tracked_validate,
    )
    monkeypatch.setattr(
        evidence_sources,
        "_html_visible_text",
        tracked_html_visible_text,
    )
    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )

    evidence = source_fetcher._fetch_work_identity_evidence(
        {
            "canonical_identity": {
                "kind": "doi",
                "value": metadata["doi"],
            }
        },
        {"authoritative_retrieval_route": route_spec},
        object(),
        bibliographic_metadata={
            key: value for key, value in metadata.items() if key != "doi"
        },
    )
    events_at_return = list(events)

    assert events_at_return == expected_events
    assert evidence["descriptor"]["payload_sha256"] == expected_sha256
    assert evidence["descriptor"]["payload_byte_length"] == len(raw_payload)


@pytest.mark.parametrize(
    ("media_type", "extension"),
    [
        ("application/pdf", "pdf"),
        ("application/xml", "xml"),
        ("text/html", "html"),
    ],
)
def test_payload_extension_mapping_is_closed(media_type, extension):
    assert evidence_sources.payload_extension_for_media_type(media_type) == extension


def test_payload_extension_mapping_rejects_every_unknown_media_type():
    with pytest.raises(SourceEvidenceError, match="unsupported.*media type"):
        evidence_sources.payload_extension_for_media_type("text/plain")


def test_loader_rejects_payload_extension_that_disagrees_with_media_type(tmp_path):
    source_dir, source, route = _write_oup_html_source(tmp_path)
    provenance_path = source_dir / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["payload_relative_path"] = "source.pdf"
    source_dir.joinpath("source.pdf").write_bytes(OUP_HTML)
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SourceEvidenceError, match="extension"):
        load_verified_source(
            source_dir,
            expected_source=source,
            provisioning_route=route,
        )


def test_loader_rejects_query_fragment_or_userinfo_in_serialized_retrieval_url(
    tmp_path,
):
    source_dir, source, route = _write_oup_html_source(tmp_path)
    provenance_path = source_dir / "provenance.json"
    for unsafe_url in (
        "https://oup.silverchair-cdn.com/article-minimal/1942776?token=private",
        "https://oup.silverchair-cdn.com/article-minimal/1942776#private",
        "https://user:password@oup.silverchair-cdn.com/article-minimal/1942776",
    ):
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["retrieval_metadata"]["url"] = unsafe_url
        provenance_path.write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(SourceEvidenceError, match="URL|query|fragment|userinfo"):
            load_verified_source(
                source_dir,
                expected_source=source,
                provisioning_route=route,
            )


@pytest.mark.parametrize("descriptor_location", ("retrieval", "sidecar"))
@pytest.mark.parametrize(
    "unsafe_url",
    (
        "https://api.openalex.org/works/W123456789?token=private",
        "https://api.openalex.org/works/W123456789#private",
        "https://user:password@api.openalex.org/works/W123456789",
    ),
)
def test_loader_rejects_unsafe_serialized_work_identity_url(
    tmp_path, descriptor_location, unsafe_url
):
    source_dir, route = _repository_fixture(
        tmp_path,
        legacy_evidence_url=descriptor_location == "sidecar",
    )
    if descriptor_location == "retrieval":
        descriptor_path = source_dir / "provenance.json"
        document = json.loads(descriptor_path.read_text(encoding="utf-8"))
        document["retrieval_metadata"]["work_identity_evidence"]["url"] = unsafe_url
    else:
        descriptor_path = source_dir / "work-identity.provenance.json"
        document = json.loads(descriptor_path.read_text(encoding="utf-8"))
        document["url"] = unsafe_url
    descriptor_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SourceEvidenceError, match="URL|query|fragment|userinfo"):
        load_verified_source(
            source_dir,
            expected_source=_expected_source(),
            provisioning_route=route,
        )


CREDENTIAL_SENTINEL = "TEST_ONLY_NOT_A_CREDENTIAL_7f2a9e"
MIXED_CASE_CREDENTIAL_SENTINEL = "TeSt_OnLy_MiXeD_CrEdEnTiAl_A7f3"
REDIRECT_CREDENTIAL_SENTINEL = "TEST_ONLY_REDIRECT_CREDENTIAL_d31b"
SIGNED_QUERY_SENTINEL = "TEST_ONLY_SIGNED_QUERY_91ca"
ELSEVIER_SOURCE_ID = "doi_aec03f65476f23115a77"


def _credential_route(
    *,
    source_id=ELSEVIER_SOURCE_ID,
    doi="10.1016/0022-3697(61)90053-1",
):
    route_spec = authoritative_route_for_identity({"kind": "doi", "value": doi})
    return {
        "source_id": source_id,
        "authoritative_retrieval_route": route_spec,
        "expected_media_type": route_spec["expected_media_type"],
        "access_mode": route_spec["access_mode"],
    }


def _credential_document(
    *,
    source_id=ELSEVIER_SOURCE_ID,
    authorization_mode="request_headers",
    origin="https://api.elsevier.com",
    headers=None,
):
    return {
        "schema_version": 1,
        "authorization_by_source_id": {
            source_id: {
                "authorization_mode": authorization_mode,
                "request_headers_by_origin": (
                    {origin: {"X-ELS-APIKey": CREDENTIAL_SENTINEL}}
                    if headers is None and authorization_mode == "request_headers"
                    else (headers or {})
                ),
            }
        },
    }


def _write_external_credential_file(tmp_path, document, *, mode=0o600, raw=False):
    path = tmp_path / "user-owned-request-credentials.json"
    content = document if raw else json.dumps(document, sort_keys=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)
    return path


def _load_credentials(path, *, routes=None, selected=None, cache_root=None):
    routes = routes or {ELSEVIER_SOURCE_ID: _credential_route()}
    selected = selected or [ELSEVIER_SOURCE_ID]
    return source_fetcher._load_request_authorizations(
        path,
        selected_source_ids=selected,
        route_by_id=routes,
        cache_root=cache_root or Path("/tmp/literature-source-cache-fixture"),
    )


def _recursive_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, bytes):
        yield value.decode("utf-8", errors="replace")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _recursive_strings(key)
            yield from _recursive_strings(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _recursive_strings(item)


def test_credential_loader_accepts_external_owned_mode_0600_exact_source_profile(
    tmp_path,
):
    path = _write_external_credential_file(tmp_path, _credential_document())
    loaded = _load_credentials(path)
    assert loaded == {
        ELSEVIER_SOURCE_ID: {
            "authorization_mode": "request_headers",
            "request_headers_by_origin": {
                "https://api.elsevier.com": {
                    "X-ELS-APIKey": CREDENTIAL_SENTINEL
                }
            },
        }
    }


@pytest.mark.parametrize(
    ("doi", "source_id"),
    [
        ("10.1016/0022-3697(61)90053-1", ELSEVIER_SOURCE_ID),
        ("10.1088/0953-8984/7/1/008", "doi_3c0cd7d12c74eed185ff"),
    ],
)
def test_institution_network_is_accepted_only_for_eligible_access_modes(
    tmp_path, doi, source_id
):
    route = _credential_route(source_id=source_id, doi=doi)
    path = _write_external_credential_file(
        tmp_path,
        _credential_document(
            source_id=source_id,
            authorization_mode="institution_network",
            headers={},
        ),
    )
    assert _load_credentials(
        path,
        routes={source_id: route},
        selected=[source_id],
    )[source_id] == {
        "authorization_mode": "institution_network",
        "request_headers_by_origin": {},
    }


def test_institution_network_is_rejected_for_authenticated_session(tmp_path):
    source_id = "doi_95a1148cb5d14b4d9680"
    route = _credential_route(source_id=source_id, doi="10.1038/nature25482")
    path = _write_external_credential_file(
        tmp_path,
        _credential_document(
            source_id=source_id,
            authorization_mode="institution_network",
            headers={},
        ),
    )
    with pytest.raises(SourceEvidenceError, match="authorization mode"):
        _load_credentials(path, routes={source_id: route}, selected=[source_id])


@pytest.mark.parametrize(
    "mutation",
    (
        "schema_version",
        "top_level_field",
        "entry_field",
        "unknown_mode",
        "empty_request_headers",
        "nonempty_institution_headers",
        "http_origin",
        "origin_with_path",
        "nonallowlisted_origin",
        "unknown_header",
        "nonstring_header_value",
        "empty_header_value",
    ),
)
def test_credential_loader_rejects_closed_schema_and_policy_violations(
    tmp_path, mutation
):
    document = _credential_document()
    entry = document["authorization_by_source_id"][ELSEVIER_SOURCE_ID]
    if mutation == "schema_version":
        document["schema_version"] = 2
    elif mutation == "top_level_field":
        document["unexpected"] = True
    elif mutation == "entry_field":
        entry["unexpected"] = True
    elif mutation == "unknown_mode":
        entry["authorization_mode"] = "ambient_magic"
    elif mutation == "empty_request_headers":
        entry["request_headers_by_origin"] = {}
    elif mutation == "nonempty_institution_headers":
        entry["authorization_mode"] = "institution_network"
    elif mutation == "http_origin":
        entry["request_headers_by_origin"] = {
            "http://api.elsevier.com": {"X-ELS-APIKey": CREDENTIAL_SENTINEL}
        }
    elif mutation == "origin_with_path":
        entry["request_headers_by_origin"] = {
            "https://api.elsevier.com/content": {
                "X-ELS-APIKey": CREDENTIAL_SENTINEL
            }
        }
    elif mutation == "nonallowlisted_origin":
        entry["request_headers_by_origin"] = {
            "https://example.invalid": {"X-ELS-APIKey": CREDENTIAL_SENTINEL}
        }
    elif mutation == "unknown_header":
        entry["request_headers_by_origin"] = {
            "https://api.elsevier.com": {"Accept": CREDENTIAL_SENTINEL}
        }
    elif mutation == "nonstring_header_value":
        entry["request_headers_by_origin"] = {
            "https://api.elsevier.com": {"X-ELS-APIKey": 17}
        }
    else:
        entry["request_headers_by_origin"] = {
            "https://api.elsevier.com": {"X-ELS-APIKey": "  "}
        }
    path = _write_external_credential_file(tmp_path, document)
    with pytest.raises(SourceEvidenceError, match="credential|authorization|origin|header"):
        _load_credentials(path)


def test_credential_loader_rejects_duplicate_case_header_names(tmp_path):
    raw = """{
      "schema_version": 1,
      "authorization_by_source_id": {
        "doi_aec03f65476f23115a77": {
          "authorization_mode": "request_headers",
          "request_headers_by_origin": {
            "https://api.elsevier.com": {
              "Authorization": "TEST_ONLY_NOT_A_CREDENTIAL_7f2a9e",
              "authorization": "TEST_ONLY_NOT_A_CREDENTIAL_7f2a9e"
            }
          }
        }
      }
    }"""
    path = _write_external_credential_file(tmp_path, raw, raw=True)
    with pytest.raises(SourceEvidenceError, match="header"):
        _load_credentials(path)


@pytest.mark.parametrize("mode", (0o604, 0o640, 0o644))
def test_credential_loader_rejects_group_or_other_permission_bits(tmp_path, mode):
    path = _write_external_credential_file(
        tmp_path, _credential_document(), mode=mode
    )
    with pytest.raises(SourceEvidenceError, match="permission"):
        _load_credentials(path)


def test_credential_loader_rejects_symlink_and_wrong_owner(tmp_path, monkeypatch):
    target = _write_external_credential_file(tmp_path, _credential_document())
    link = tmp_path / "credential-link.json"
    link.symlink_to(target)
    with pytest.raises(SourceEvidenceError, match="symlink"):
        _load_credentials(link)

    actual_uid = os.getuid()
    monkeypatch.setattr(source_fetcher.os, "getuid", lambda: actual_uid + 1)
    with pytest.raises(SourceEvidenceError, match="owner"):
        _load_credentials(target)


def test_credential_loader_rejects_file_replaced_between_check_and_open(
    tmp_path, monkeypatch
):
    target = _write_external_credential_file(tmp_path, _credential_document())
    substitute = tmp_path / "substituted-request-credentials.json"
    substitute.write_text(
        json.dumps(_credential_document(), sort_keys=True),
        encoding="utf-8",
    )
    substitute.chmod(0o600)
    real_open = os.open

    def open_substitute(path, flags, *args, **kwargs):
        return real_open(substitute, flags, *args, **kwargs)

    monkeypatch.setattr(source_fetcher.os, "open", open_substitute)
    with pytest.raises(SourceEvidenceError, match="changed|safely"):
        _load_credentials(target)


@pytest.mark.parametrize("location", ("project", "cache"))
def test_credential_loader_rejects_paths_inside_project_or_cache_without_opening(
    tmp_path, location
):
    cache_root = tmp_path / "isolated-cache"
    path = (
        PROJECT_ROOT / "never-created-credential.json"
        if location == "project"
        else cache_root / "never-created-credential.json"
    )
    assert not path.exists()
    with pytest.raises(SourceEvidenceError, match="outside"):
        _load_credentials(path, cache_root=cache_root)
    assert not path.exists()


def test_credential_loader_rejects_git_root_sibling_before_file_inspection(
    tmp_path, monkeypatch
):
    repository_root = PROJECT_ROOT.parent
    assert repository_root.joinpath(".git").exists()
    candidate = repository_root / "never-created-repository-sibling-credential.json"
    assert not candidate.exists()
    inspected = []
    real_lstat = Path.lstat

    def tracked_lstat(path):
        inspected.append(path)
        return real_lstat(path)

    monkeypatch.setattr(Path, "lstat", tracked_lstat)
    with pytest.raises(SourceEvidenceError, match="outside the repository"):
        _load_credentials(
            candidate,
            cache_root=tmp_path / "isolated-cache",
        )

    assert candidate not in inspected
    assert not candidate.exists()


def test_credential_loader_requires_exact_selected_nonunattended_source_entries(
    tmp_path,
):
    empty_path = _write_external_credential_file(
        tmp_path,
        {"schema_version": 1, "authorization_by_source_id": {}},
    )
    with pytest.raises(SourceEvidenceError, match=ELSEVIER_SOURCE_ID):
        _load_credentials(empty_path)

    extra_id = "doi_3c0cd7d12c74eed185ff"
    document = _credential_document()
    document["authorization_by_source_id"][extra_id] = {
        "authorization_mode": "institution_network",
        "request_headers_by_origin": {},
    }
    extra_path = tmp_path / "broad-profile.json"
    extra_path.write_text(json.dumps(document), encoding="utf-8")
    extra_path.chmod(0o600)
    routes = {
        ELSEVIER_SOURCE_ID: _credential_route(),
        extra_id: _credential_route(
            source_id=extra_id, doi="10.1088/0953-8984/7/1/008"
        ),
    }
    with pytest.raises(SourceEvidenceError, match="unselected"):
        _load_credentials(extra_path, routes=routes, selected=[ELSEVIER_SOURCE_ID])


def test_credential_loader_rejects_authorization_for_unattended_source(tmp_path):
    source_id = "doi_422f517c2d9549fef833"
    route = _credential_route(
        source_id=source_id, doi="10.1103/physrevb.83.155120"
    )
    path = _write_external_credential_file(
        tmp_path,
        _credential_document(
            source_id=source_id,
            origin="https://harvest.aps.org",
        ),
    )
    with pytest.raises(SourceEvidenceError, match="unattended"):
        _load_credentials(path, routes={source_id: route}, selected=[source_id])


def test_access_mode_all_requires_credentials_before_cache_or_network(
    tmp_path, monkeypatch
):
    source = {
        "source_id": ELSEVIER_SOURCE_ID,
        "canonical_identity": {
            "kind": "doi",
            "value": "10.1016/0022-3697(61)90053-1",
        },
        "canonical_url": "https://doi.org/10.1016/0022-3697(61)90053-1",
        "benchmark_names": ["fixture"],
    }
    route = _credential_route()
    monkeypatch.setattr(
        source_fetcher,
        "load_and_validate_inventory",
        lambda: SimpleNamespace(source_index=(source,), source_provisioning=(route,)),
    )
    monkeypatch.setattr(
        source_fetcher,
        "_fetch_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("network/cache path reached before credential validation")
        ),
    )
    with pytest.raises(SystemExit):
        source_fetcher.main(
            [
                "--source-id",
                ELSEVIER_SOURCE_ID,
                "--access-mode",
                "all",
                "--cache-root",
                str(tmp_path / "cache"),
            ]
        )
    assert not (tmp_path / "cache").exists()


def test_access_mode_all_offline_verification_never_loads_credentials(
    tmp_path, monkeypatch, capsys
):
    source = {
        "source_id": ELSEVIER_SOURCE_ID,
        "canonical_identity": {
            "kind": "doi",
            "value": "10.1016/0022-3697(61)90053-1",
        },
        "canonical_url": "https://doi.org/10.1016/0022-3697(61)90053-1",
        "benchmark_names": ["fixture"],
    }
    route = _credential_route()
    monkeypatch.setattr(
        source_fetcher,
        "load_and_validate_inventory",
        lambda: SimpleNamespace(source_index=(source,), source_provisioning=(route,)),
    )
    monkeypatch.setattr(
        source_fetcher,
        "_load_request_authorizations",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("offline verification loaded credential input")
        ),
    )
    monkeypatch.setattr(
        source_fetcher,
        "_verify_cached_source",
        lambda *args, **kwargs: {
            "source_id": ELSEVIER_SOURCE_ID,
            "status": "verified",
            "detail": "fixture-hash",
        },
    )

    assert source_fetcher.main(
        [
            "--source-id",
            ELSEVIER_SOURCE_ID,
            "--access-mode",
            "all",
            "--verify-offline",
            "--cache-root",
            str(tmp_path / "cache"),
        ]
    ) == 0
    assert '"status": "verified"' in capsys.readouterr().out


def _header_dict(request):
    return {key.casefold(): value for key, value in request.header_items()}


def test_credential_redirect_policy_strips_and_exactly_reapplies_profiles():
    profile = {
        "authorization_mode": "request_headers",
        "request_headers_by_origin": {
            "https://api.elsevier.com": {
                "X-ELS-APIKey": CREDENTIAL_SENTINEL
            },
            "https://redirect.elsevier.com": {
                "Authorization": REDIRECT_CREDENTIAL_SENTINEL
            },
        },
    }
    handler = source_fetcher._CredentialRedirectHandler(profile)
    initial = Request(
        "https://api.elsevier.com/content/article",
        headers={
            "Accept": "application/xml",
            "User-Agent": "fixture",
            "X-ELS-APIKey": CREDENTIAL_SENTINEL,
        },
    )
    unprofiled = handler.redirect_request(
        initial,
        None,
        302,
        "Found",
        {},
        "https://crossref.org/works/redirected",
    )
    assert CREDENTIAL_SENTINEL not in _header_dict(unprofiled).values()
    assert REDIRECT_CREDENTIAL_SENTINEL not in _header_dict(unprofiled).values()

    reprofiled = handler.redirect_request(
        initial,
        None,
        302,
        "Found",
        {},
        "https://redirect.elsevier.com/final",
    )
    headers = _header_dict(reprofiled)
    assert CREDENTIAL_SENTINEL not in headers.values()
    assert headers["authorization"] == REDIRECT_CREDENTIAL_SENTINEL


def test_credential_redirect_policy_rejects_userinfo_and_never_forwards_to_sidecars():
    profile = {
        "authorization_mode": "request_headers",
        "request_headers_by_origin": {
            "https://api.elsevier.com": {
                "X-ELS-APIKey": CREDENTIAL_SENTINEL
            }
        },
    }
    handler = source_fetcher._CredentialRedirectHandler(profile)
    initial = Request(
        "https://api.elsevier.com/content/article",
        headers={"X-ELS-APIKey": CREDENTIAL_SENTINEL},
    )
    with pytest.raises(SourceEvidenceError, match="userinfo"):
        handler.redirect_request(
            initial,
            None,
            302,
            "Found",
            {},
            "https://user:password@api.elsevier.com/private",
        )
    for sidecar_url in (
        "https://api.crossref.org/works/fixture",
        "https://export.arxiv.org/api/query?id_list=fixture",
        "https://api.core.ac.uk/v3/outputs/572184419",
        "https://www.lptmc.jussieu.fr/users/maillard",
    ):
        redirected = handler.redirect_request(
            initial, None, 302, "Found", {}, sidecar_url
        )
        assert CREDENTIAL_SENTINEL not in _header_dict(redirected).values()


class _SignedFixtureResponse:
    def __init__(self, body, final_url):
        self._body = body
        self.status = 200
        self.headers = {
            "Content-Type": "application/pdf",
            "ETag": f"reflected-{CREDENTIAL_SENTINEL}",
        }
        self._final_url = final_url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self._body

    def geturl(self):
        return self._final_url


def test_authenticated_download_uses_full_signed_url_only_in_memory_and_redacts_outputs(
    monkeypatch,
):
    body = _minimal_pdf("Credential-safe payload.")
    full_url = (
        "https://api.elsevier.com/content/article?signature="
        + SIGNED_QUERY_SENTINEL
        + "#private-fragment"
    )
    captured = {}

    class FixtureOpener:
        def open(self, request, timeout):
            captured["request"] = request
            return _SignedFixtureResponse(body, full_url)

    monkeypatch.setattr(source_fetcher, "build_opener", lambda *handlers: FixtureOpener())
    route = {
        "kind": "elsevier_article_api_xml",
        "url": full_url,
        "expected_media_type": "application/pdf",
        "access_mode": "api_key_or_entitlement",
    }
    profile = {
        "authorization_mode": "request_headers",
        "request_headers_by_origin": {
            "https://api.elsevier.com": {
                "X-ELS-APIKey": CREDENTIAL_SENTINEL
            }
        },
    }
    response = source_fetcher._download(
        route, object(), credential_profile=profile
    )

    assert captured["request"].full_url == full_url
    assert _header_dict(captured["request"])["x-els-apikey"] == CREDENTIAL_SENTINEL
    assert response["final_url"] == "https://api.elsevier.com/content/article"
    assert not any(
        CREDENTIAL_SENTINEL in text for text in _recursive_strings(response)
    )
    source = {
        "source_id": ELSEVIER_SOURCE_ID,
        "canonical_identity": {"kind": "doi", "value": "10.1016/example"},
        "canonical_url": "https://doi.org/10.1016/example",
    }
    provisioning = {
        "authoritative_retrieval_route": {
            "kind": "elsevier_article_api_xml",
            "artifact_identifier": "doi:10.1016/example",
            "work_identity_evidence": {
                "kind": "canonical_identity",
                "url": "https://doi.org/10.1016/example",
            },
        }
    }
    provenance = source_fetcher._build_provenance(
        source,
        provisioning,
        response,
        {
            "title": "Fixture",
            "authors": ["A. Author"],
            "venue": "Fixture",
            "publication_date": "2024-01-01",
        },
        payload_name="source.pdf",
    )
    serialized = json.dumps(provenance, sort_keys=True)
    assert CREDENTIAL_SENTINEL not in serialized
    assert REDIRECT_CREDENTIAL_SENTINEL not in serialized
    assert SIGNED_QUERY_SENTINEL not in serialized
    assert "private-fragment" not in serialized
    assert "etag" not in provenance["retrieval_metadata"]["response_headers"]


@pytest.mark.parametrize(
    "reflected_value",
    (
        MIXED_CASE_CREDENTIAL_SENTINEL.casefold(),
        MIXED_CASE_CREDENTIAL_SENTINEL.swapcase(),
    ),
)
def test_download_error_never_exposes_case_variant_from_content_type(
    monkeypatch, reflected_value
):
    body = _minimal_pdf("Credential-safe payload.")

    class FixtureOpener:
        def open(self, request, timeout):
            response = _SignedFixtureResponse(
                body,
                "https://api.elsevier.com/content/article",
            )
            response.headers = {"Content-Type": f"application/{reflected_value}"}
            return response

    monkeypatch.setattr(source_fetcher, "build_opener", lambda *handlers: FixtureOpener())
    profile = {
        "authorization_mode": "request_headers",
        "request_headers_by_origin": {
            "https://api.elsevier.com": {
                "X-ELS-APIKey": MIXED_CASE_CREDENTIAL_SENTINEL
            }
        },
    }
    with pytest.raises(SourceEvidenceError) as caught:
        source_fetcher._download(
            {
                "kind": "elsevier_article_api_xml",
                "url": "https://api.elsevier.com/content/article",
                "expected_media_type": "application/pdf",
            },
            object(),
            credential_profile=profile,
        )
    assert MIXED_CASE_CREDENTIAL_SENTINEL.casefold() not in str(caught.value).casefold()


def test_download_omits_case_insensitive_header_reflections_from_returned_mapping(
    monkeypatch,
):
    body = _minimal_pdf("Credential-safe payload.")

    class FixtureOpener:
        def open(self, request, timeout):
            response = _SignedFixtureResponse(
                body,
                "https://api.elsevier.com/content/article",
            )
            response.headers = {
                "Content-Type": "application/pdf",
                "ETag": "reflected-" + MIXED_CASE_CREDENTIAL_SENTINEL.swapcase(),
                "Last-Modified": MIXED_CASE_CREDENTIAL_SENTINEL.casefold(),
            }
            return response

    monkeypatch.setattr(source_fetcher, "build_opener", lambda *handlers: FixtureOpener())
    profile = {
        "authorization_mode": "request_headers",
        "request_headers_by_origin": {
            "https://api.elsevier.com": {
                "X-ELS-APIKey": MIXED_CASE_CREDENTIAL_SENTINEL
            }
        },
    }
    response = source_fetcher._download(
        {
            "kind": "elsevier_article_api_xml",
            "url": "https://api.elsevier.com/content/article",
            "expected_media_type": "application/pdf",
        },
        object(),
        credential_profile=profile,
    )
    serialized = " ".join(_recursive_strings(response)).casefold()
    assert MIXED_CASE_CREDENTIAL_SENTINEL.casefold() not in serialized


def test_download_rejects_active_credential_in_final_path_or_payload(
    monkeypatch,
):
    profile = {
        "authorization_mode": "request_headers",
        "request_headers_by_origin": {
            "https://api.elsevier.com": {
                "X-ELS-APIKey": MIXED_CASE_CREDENTIAL_SENTINEL
            }
        },
    }
    route = {
        "kind": "elsevier_article_api_xml",
        "url": (
            "https://api.elsevier.com/content/article?signature="
            + SIGNED_QUERY_SENTINEL
        ),
        "expected_media_type": "application/pdf",
    }
    cases = (
        (
            _minimal_pdf("Credential-safe payload."),
            "https://api.elsevier.com/content/"
            + MIXED_CASE_CREDENTIAL_SENTINEL.swapcase()
            + "/article?signature="
            + SIGNED_QUERY_SENTINEL,
        ),
        (
            _minimal_pdf(
                "Reflected " + MIXED_CASE_CREDENTIAL_SENTINEL.swapcase()
            ),
            "https://api.elsevier.com/content/article?signature="
            + SIGNED_QUERY_SENTINEL,
        ),
    )
    for body, final_url in cases:
        class FixtureOpener:
            def open(self, request, timeout):
                return _SignedFixtureResponse(body, final_url)

        monkeypatch.setattr(
            source_fetcher,
            "build_opener",
            lambda *handlers: FixtureOpener(),
        )
        with pytest.raises(SourceEvidenceError) as caught:
            source_fetcher._download(
                route,
                object(),
                credential_profile=profile,
            )
        rendered = str(caught.value).casefold()
        assert MIXED_CASE_CREDENTIAL_SENTINEL.casefold() not in rendered
        assert SIGNED_QUERY_SENTINEL.casefold() not in rendered


def test_fetch_source_failure_outcome_case_insensitively_redacts_secret(
    tmp_path, monkeypatch
):
    source_id = ELSEVIER_SOURCE_ID
    source = {"source_id": source_id}
    route_spec = _credential_route()["authoritative_retrieval_route"]
    route = {
        "source_id": source_id,
        "authoritative_retrieval_route": route_spec,
        "expected_media_type": route_spec["expected_media_type"],
        "access_mode": route_spec["access_mode"],
    }
    profile = {
        "authorization_mode": "request_headers",
        "request_headers_by_origin": {
            "https://api.elsevier.com": {
                "X-ELS-APIKey": MIXED_CASE_CREDENTIAL_SENTINEL
            }
        },
    }
    monkeypatch.setattr(source_fetcher, "_ssl_context", lambda ca_bundle: object())
    monkeypatch.setattr(
        source_fetcher,
        "_download",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            SourceEvidenceError(
                "untrusted response " + MIXED_CASE_CREDENTIAL_SENTINEL.swapcase()
            )
        ),
    )
    outcome = source_fetcher._fetch_source(
        tmp_path / "cache",
        source,
        route,
        ca_bundle=Path("/unused"),
        resume=False,
        credential_profile=profile,
    )
    assert outcome["status"] == "failed"
    assert MIXED_CASE_CREDENTIAL_SENTINEL.casefold() not in (
        " ".join(_recursive_strings(outcome)).casefold()
    )
    assert not (tmp_path / "cache" / source_id).exists()


def test_main_stdout_stderr_drop_secret_case_variants_and_internal_profile(
    tmp_path, monkeypatch, capsys
):
    source = {
        "source_id": ELSEVIER_SOURCE_ID,
        "canonical_identity": {
            "kind": "doi",
            "value": "10.1016/0022-3697(61)90053-1",
        },
        "canonical_url": "https://doi.org/10.1016/0022-3697(61)90053-1",
        "benchmark_names": ["fixture"],
    }
    route = _credential_route()
    profile = {
        "authorization_mode": "request_headers",
        "request_headers_by_origin": {
            "https://api.elsevier.com": {
                "X-ELS-APIKey": MIXED_CASE_CREDENTIAL_SENTINEL
            }
        },
    }
    monkeypatch.setattr(
        source_fetcher,
        "load_and_validate_inventory",
        lambda: SimpleNamespace(source_index=(source,), source_provisioning=(route,)),
    )
    monkeypatch.setattr(
        source_fetcher,
        "_load_request_authorizations",
        lambda *args, **kwargs: {ELSEVIER_SOURCE_ID: profile},
    )
    monkeypatch.setattr(
        source_fetcher,
        "_fetch_source",
        lambda *args, **kwargs: {
            "source_id": ELSEVIER_SOURCE_ID,
            "status": "failed",
            "detail": (
                "https://api.elsevier.com/content/"
                + MIXED_CASE_CREDENTIAL_SENTINEL.casefold()
                + "/article?signature="
                + SIGNED_QUERY_SENTINEL
            ),
            "request_headers_by_origin": profile["request_headers_by_origin"],
        },
    )
    assert source_fetcher.main(
        [
            "--source-id",
            ELSEVIER_SOURCE_ID,
            "--access-mode",
            "all",
            "--cache-root",
            str(tmp_path / "cache"),
        ]
    ) == 1
    streams = capsys.readouterr()
    rendered = (streams.out + streams.err).casefold()
    assert MIXED_CASE_CREDENTIAL_SENTINEL.casefold() not in rendered
    assert SIGNED_QUERY_SENTINEL.casefold() not in rendered
    assert "request_headers_by_origin" not in rendered


def test_provenance_omits_case_insensitive_header_reflections(monkeypatch):
    monkeypatch.setattr(source_fetcher, "_pdftotext_version", lambda: "fixture")
    source = {
        "source_id": ELSEVIER_SOURCE_ID,
        "canonical_identity": {"kind": "doi", "value": "10.1016/example"},
        "canonical_url": "https://doi.org/10.1016/example",
    }
    route = {
        "authoritative_retrieval_route": {
            "kind": "elsevier_article_api_xml",
            "artifact_identifier": "doi:10.1016/example",
            "work_identity_evidence": {
                "kind": "canonical_identity",
                "url": "https://doi.org/10.1016/example",
            },
        }
    }
    response = {
        "body": _minimal_pdf("Credential-safe payload."),
        "final_url": "https://api.elsevier.com/content/article",
        "status": 200,
        "headers": {
            "Content-Type": "application/pdf",
            "ETag": MIXED_CASE_CREDENTIAL_SENTINEL.swapcase(),
            "Last-Modified": MIXED_CASE_CREDENTIAL_SENTINEL.casefold(),
        },
        "media_type": "application/pdf",
        "credential_values": (MIXED_CASE_CREDENTIAL_SENTINEL,),
    }
    provenance = source_fetcher._build_provenance(
        source,
        route,
        response,
        {
            "title": "Fixture",
            "authors": ["A. Author"],
            "venue": "Fixture",
            "publication_date": "2024-01-01",
        },
        payload_name="source.pdf",
    )
    assert MIXED_CASE_CREDENTIAL_SENTINEL.casefold() not in (
        json.dumps(provenance, sort_keys=True).casefold()
    )


def test_provenance_rejects_active_credential_in_serialized_final_path(monkeypatch):
    monkeypatch.setattr(source_fetcher, "_pdftotext_version", lambda: "fixture")
    source = {
        "source_id": ELSEVIER_SOURCE_ID,
        "canonical_identity": {"kind": "doi", "value": "10.1016/example"},
        "canonical_url": "https://doi.org/10.1016/example",
    }
    route = {
        "authoritative_retrieval_route": {
            "kind": "elsevier_article_api_xml",
            "artifact_identifier": "doi:10.1016/example",
            "work_identity_evidence": {
                "kind": "canonical_identity",
                "url": "https://doi.org/10.101/example",
            },
        }
    }
    response = {
        "body": _minimal_pdf("Credential-safe payload."),
        "final_url": (
            "https://api.elsevier.com/content/"
            + MIXED_CASE_CREDENTIAL_SENTINEL.swapcase()
            + "/article"
        ),
        "status": 200,
        "headers": {"Content-Type": "application/pdf"},
        "media_type": "application/pdf",
        "credential_values": (MIXED_CASE_CREDENTIAL_SENTINEL,),
    }
    with pytest.raises(SourceEvidenceError) as caught:
        source_fetcher._build_provenance(
            source,
            route,
            response,
            {
                "title": "Fixture",
                "authors": ["A. Author"],
                "venue": "Fixture",
                "publication_date": "2024-01-01",
            },
            payload_name="source.pdf",
        )
    assert MIXED_CASE_CREDENTIAL_SENTINEL.casefold() not in str(caught.value).casefold()


def test_work_identity_request_uses_full_signed_url_but_descriptor_is_sanitized(
    monkeypatch,
):
    route_spec = copy.deepcopy(_author_garel_route())
    full_url = (
        route_spec["work_identity_evidence"]["url"]
        + "?signature="
        + SIGNED_QUERY_SENTINEL
        + "#private-fragment"
    )
    route_spec["work_identity_evidence"]["url"] = full_url
    captured = {}

    class FixtureOpener:
        def open(self, request, timeout):
            captured["request"] = request
            return _FixtureHTTPResponse(
                AUTHOR_GAREL_PAGE,
                content_type="text/html",
                final_url=request.full_url,
            )

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )
    evidence = source_fetcher._fetch_work_identity_evidence(
        {
            "canonical_identity": {
                "kind": "doi",
                "value": "10.1088/0305-4470/16/10/023",
            }
        },
        {"authoritative_retrieval_route": route_spec},
        object(),
        bibliographic_metadata={
            "title": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["title"],
            "authors": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["authors"],
        },
    )

    assert captured["request"].full_url == full_url
    request_headers = _header_dict(captured["request"])
    assert not _CREDENTIAL_HEADER_CASEFOLDS.intersection(request_headers)
    assert evidence["descriptor"]["url"] == (
        "https://www.lptmc.jussieu.fr/users/maillard"
    )
    serialized = json.dumps(evidence["descriptor"], sort_keys=True)
    assert SIGNED_QUERY_SENTINEL not in serialized
    assert "private-fragment" not in serialized


def test_work_identity_declared_userinfo_is_rejected_before_open(monkeypatch):
    route_spec = copy.deepcopy(_author_garel_route())
    route_spec["work_identity_evidence"]["url"] = (
        "https://user:password@www.lptmc.jussieu.fr/users/maillard"
    )
    opened = []

    class FixtureOpener:
        def open(self, request, timeout):
            opened.append(request.full_url)
            return _FixtureHTTPResponse(
                AUTHOR_GAREL_PAGE,
                content_type="text/html",
                final_url=request.full_url,
            )

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )
    monkeypatch.setattr(
        source_fetcher,
        "urlopen",
        lambda request, **kwargs: FixtureOpener().open(request, kwargs["timeout"]),
    )
    with pytest.raises(SourceEvidenceError, match="userinfo"):
        source_fetcher._fetch_work_identity_evidence(
            {
                "canonical_identity": {
                    "kind": "doi",
                    "value": "10.1088/0305-4470/16/10/023",
                }
            },
            {"authoritative_retrieval_route": route_spec},
            object(),
            bibliographic_metadata={
                "title": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["title"],
                "authors": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["authors"],
            },
        )
    assert opened == []


def test_work_identity_redirect_userinfo_is_rejected_before_unsafe_target_open(
    monkeypatch,
):
    route_spec = copy.deepcopy(_author_garel_route())
    unsafe_url = "https://user:password@sidecar.example.invalid/private"
    opened_targets = []

    def opener_factory(*handlers):
        redirect_handler = next(
            handler
            for handler in handlers
            if isinstance(handler, source_fetcher._CredentialRedirectHandler)
        )
        assert redirect_handler.credential_profile is None

        class FixtureOpener:
            def open(self, request, timeout):
                redirected = redirect_handler.redirect_request(
                    request,
                    None,
                    302,
                    "Found",
                    {},
                    unsafe_url,
                )
                opened_targets.append(redirected.full_url)
                return _FixtureHTTPResponse(
                    AUTHOR_GAREL_PAGE,
                    content_type="text/html",
                    final_url=redirected.full_url,
                )

        return FixtureOpener()

    monkeypatch.setattr(source_fetcher, "build_opener", opener_factory)
    monkeypatch.setattr(
        source_fetcher,
        "urlopen",
        lambda request, **kwargs: _FixtureHTTPResponse(
            AUTHOR_GAREL_PAGE,
            content_type="text/html",
            final_url=request.full_url,
        ),
    )
    with pytest.raises(SourceEvidenceError, match="userinfo"):
        source_fetcher._fetch_work_identity_evidence(
            {
                "canonical_identity": {
                    "kind": "doi",
                    "value": "10.1088/0305-4470/16/10/023",
                }
            },
            {"authoritative_retrieval_route": route_spec},
            object(),
            bibliographic_metadata={
                "title": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["title"],
                "authors": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["authors"],
            },
        )
    assert opened_targets == []


def test_work_identity_final_userinfo_is_rejected(monkeypatch):
    route_spec = copy.deepcopy(_author_garel_route())
    unsafe_final_url = "https://user:password@sidecar.example.invalid/private"

    class FixtureOpener:
        def open(self, request, timeout):
            return _FixtureHTTPResponse(
                AUTHOR_GAREL_PAGE,
                content_type="text/html",
                final_url=unsafe_final_url,
            )

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )
    monkeypatch.setattr(
        source_fetcher,
        "urlopen",
        lambda request, **kwargs: FixtureOpener().open(request, kwargs["timeout"]),
    )
    with pytest.raises(SourceEvidenceError, match="userinfo"):
        source_fetcher._fetch_work_identity_evidence(
            {
                "canonical_identity": {
                    "kind": "doi",
                    "value": "10.1088/0305-4470/16/10/023",
                }
            },
            {"authoritative_retrieval_route": route_spec},
            object(),
            bibliographic_metadata={
                "title": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["title"],
                "authors": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["authors"],
            },
        )


_CREDENTIAL_HEADER_CASEFOLDS = {
    "cookie",
    "authorization",
    "x-els-apikey",
    "x-els-insttoken",
}


def test_exact_fourteen_restricted_routes_have_closed_official_origin_allowlists():
    routes = _registry_routes_by_identity()
    restricted = [
        route for route in routes.values() if route["access_mode"] != "unattended"
    ]
    expected_by_kind = {
        "elsevier_article_api_xml": {"https://api.elsevier.com"},
        "nature_article_pdf": {
            "https://www.nature.com",
            "https://idp.nature.com",
        },
        "springer_content_pdf": {"https://link.springer.com"},
        "iop_article_pdf": {"https://iopscience.iop.org"},
        "epl_iop_article_pdf": {"https://iopscience.iop.org"},
        "science_article_pdf": {"https://www.science.org"},
        "aip_article_discovery": {"https://doi.org", "https://pubs.aip.org"},
        "acs_article_pdf": {"https://pubs.acs.org"},
        "jpsj_article_pdf": {"https://journals.jps.jp"},
    }
    assert len(restricted) == 14
    for route_spec in restricted:
        route = {"authoritative_retrieval_route": route_spec}
        assert source_fetcher._allowed_authorization_origins(route) == (
            expected_by_kind[route_spec["kind"]]
        )


@pytest.mark.parametrize("forbidden_header", ("Accept", "User-Agent", "Host", "URL"))
def test_credential_profile_cannot_override_request_control_headers(
    tmp_path, forbidden_header
):
    document = _credential_document()
    document["authorization_by_source_id"][ELSEVIER_SOURCE_ID][
        "request_headers_by_origin"
    ] = {
        "https://api.elsevier.com": {
            forbidden_header: CREDENTIAL_SENTINEL
        }
    }
    path = _write_external_credential_file(tmp_path, document)
    with pytest.raises(SourceEvidenceError, match="closed allowlist"):
        _load_credentials(path)


def test_credential_loader_rejects_unknown_source_id(tmp_path):
    unknown_id = "doi_00000000000000000000"
    path = _write_external_credential_file(
        tmp_path,
        _credential_document(source_id=unknown_id),
    )
    with pytest.raises(SourceEvidenceError, match="unknown source ID"):
        _load_credentials(path)


def test_cli_passes_only_exact_selected_source_profile_and_prints_no_secret(
    tmp_path, monkeypatch, capsys
):
    source = {
        "source_id": ELSEVIER_SOURCE_ID,
        "canonical_identity": {
            "kind": "doi",
            "value": "10.1016/0022-3697(61)90053-1",
        },
        "canonical_url": "https://doi.org/10.1016/0022-3697(61)90053-1",
        "benchmark_names": ["fixture"],
    }
    route = _credential_route()
    path = _write_external_credential_file(tmp_path, _credential_document())
    captured = {}
    monkeypatch.setattr(
        source_fetcher,
        "load_and_validate_inventory",
        lambda: SimpleNamespace(source_index=(source,), source_provisioning=(route,)),
    )

    def fake_fetch(cache_root, selected_source, selected_route, **kwargs):
        captured["profile"] = kwargs["credential_profile"]
        return {"source_id": ELSEVIER_SOURCE_ID, "status": "acquired", "detail": "ok"}

    monkeypatch.setattr(source_fetcher, "_fetch_source", fake_fetch)
    assert source_fetcher.main(
        [
            "--source-id",
            ELSEVIER_SOURCE_ID,
            "--access-mode",
            "all",
            "--request-credential-file",
            str(path),
            "--cache-root",
            str(tmp_path / "cache"),
        ]
    ) == 0
    assert captured["profile"]["request_headers_by_origin"] == {
        "https://api.elsevier.com": {"X-ELS-APIKey": CREDENTIAL_SENTINEL}
    }
    streams = capsys.readouterr()
    assert CREDENTIAL_SENTINEL not in streams.out + streams.err


def test_existing_cache_and_sidecar_files_are_never_overwritten(tmp_path):
    source_id = "doi_e49cda761520424da334"
    cache_root = tmp_path / "cache"
    source_dir = cache_root / source_id
    source_dir.mkdir(parents=True)
    sentinel_path = source_dir / "user-owned-sentinel.txt"
    sentinel_path.write_text("preserve-me", encoding="utf-8")
    outcome = source_fetcher._fetch_source(
        cache_root,
        {"source_id": source_id},
        {"source_id": source_id},
        ca_bundle=Path("/not-used"),
        resume=False,
    )
    assert outcome["status"] == "failed"
    assert outcome["detail"] == "cache directory already exists"
    assert sentinel_path.read_text(encoding="utf-8") == "preserve-me"
    assert list(source_dir.iterdir()) == [sentinel_path]

    existing_sidecar = source_dir / "work-identity.json"
    existing_sidecar.write_bytes(b"user-owned-sidecar")
    with pytest.raises(FileExistsError):
        source_fetcher._write_work_identity_sidecars(
            source_dir,
            {
                "payload": b"replacement",
                "descriptor": {
                    "payload_relative_path": "work-identity.json",
                },
            },
        )
    assert existing_sidecar.read_bytes() == b"user-owned-sidecar"


def test_fetch_failure_reports_exact_new_cache_directory_without_creating_it(
    tmp_path, monkeypatch
):
    source_id = "doi_e49cda761520424da334"
    cache_root = tmp_path / "cache"
    source_dir = cache_root / source_id
    monkeypatch.setattr(
        source_fetcher,
        "_ssl_context",
        lambda ca_bundle: (_ for _ in ()).throw(SourceEvidenceError("TLS unavailable")),
    )
    outcome = source_fetcher._fetch_source(
        cache_root,
        {"source_id": source_id},
        {"source_id": source_id},
        ca_bundle=Path("/fixture"),
        resume=False,
    )
    assert outcome == {
        "source_id": source_id,
        "status": "failed",
        "detail": f"new cache directory {source_dir} failed: TLS unavailable",
    }
    assert not source_dir.exists()


def test_authenticated_download_rejects_declared_and_final_userinfo(monkeypatch):
    profile = {
        "authorization_mode": "request_headers",
        "request_headers_by_origin": {
            "https://api.elsevier.com": {
                "X-ELS-APIKey": CREDENTIAL_SENTINEL
            }
        },
    }
    with pytest.raises(SourceEvidenceError, match="userinfo"):
        source_fetcher._download(
            {
                "kind": "elsevier_article_api_xml",
                "url": "https://user:password@api.elsevier.com/content/article",
                "expected_media_type": "application/xml",
            },
            object(),
            credential_profile=profile,
        )

    body = _minimal_pdf("Credential-safe payload.")

    class FixtureOpener:
        def open(self, request, timeout):
            return _SignedFixtureResponse(
                body,
                "https://user:password@api.elsevier.com/content/article",
            )

    monkeypatch.setattr(source_fetcher, "build_opener", lambda *handlers: FixtureOpener())
    with pytest.raises(SourceEvidenceError, match="userinfo"):
        source_fetcher._download(
            {
                "kind": "elsevier_article_api_xml",
                "url": "https://api.elsevier.com/content/article",
                "expected_media_type": "application/pdf",
            },
            object(),
            credential_profile=profile,
        )


def test_credential_sentinels_never_appear_in_success_or_failure_outcomes(
    capsys,
):
    success = source_fetcher._outcome(
        ELSEVIER_SOURCE_ID,
        "acquired",
        "https://api.elsevier.com/content/article?signature=" + SIGNED_QUERY_SENTINEL,
        sensitive_values=(CREDENTIAL_SENTINEL,),
    )
    failure = source_fetcher._outcome(
        ELSEVIER_SOURCE_ID,
        "failed",
        "request failed with reflected value " + CREDENTIAL_SENTINEL,
        sensitive_values=(CREDENTIAL_SENTINEL,),
    )
    print(json.dumps(success, sort_keys=True))
    print(json.dumps(failure, sort_keys=True), file=sys.stderr)
    captured = capsys.readouterr()
    combined = captured.out + captured.err + json.dumps([success, failure])
    assert CREDENTIAL_SENTINEL not in combined
    assert REDIRECT_CREDENTIAL_SENTINEL not in combined
    assert SIGNED_QUERY_SENTINEL not in combined


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


def _oup_html_route():
    return authoritative_route_for_identity(
        {"kind": "doi", "value": "10.1143/ptp.5.2.177"}
    )


def _write_oup_html_source(tmp_path, payload=OUP_HTML):
    source_id = "doi_f334ed253565110358b3"
    route_spec = _oup_html_route()
    source = {
        "source_id": source_id,
        "canonical_identity": {"kind": "doi", "value": "10.1143/ptp.5.2.177"},
        "canonical_url": "https://doi.org/10.1143/ptp.5.2.177",
        "benchmark_names": [
            "honeycomb_ising_ferromagnet_exact_tc",
            "triangular_ising_ferromagnet_exact_tc",
        ],
    }
    route = {
        "source_id": source_id,
        "authoritative_retrieval_route": route_spec,
        "expected_media_type": "text/html",
        "access_mode": "unattended",
    }
    provenance = _provenance(payload)
    provenance.update(
        {
            "source_id": source_id,
            "source_identity": {
                **source["canonical_identity"],
                "canonical_url": source["canonical_url"],
            },
            "media_type": "text/html",
            "payload_relative_path": "source.html",
            "text_extraction": {
                "tool": "stdlib_html_visible_text",
                "version": 1,
                "deterministic": True,
                "arguments": [],
            },
        }
    )
    provenance["retrieval_metadata"].update(
        {
            "url": route_spec["url"],
            "method": route_spec["kind"],
            "response_headers": {"content-type": "text/html"},
            "immutable_artifact_identifier": route_spec["artifact_identifier"],
        }
    )
    source_dir = tmp_path / source_id
    source_dir.mkdir()
    source_dir.joinpath("source.html").write_bytes(payload)
    source_dir.joinpath("provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return source_dir, source, route


def test_html_download_and_offline_visible_text_are_deterministic(tmp_path):
    route_spec = _oup_html_route()
    assert validate_download_response(
        route_spec,
        status=200,
        headers={"content-type": "text/html; charset=UTF-8"},
        body=OUP_HTML,
        final_url=route_spec["url"],
    ) == "text/html"

    source_dir, source, route = _write_oup_html_source(tmp_path)
    verified = load_verified_source(
        source_dir,
        expected_source=source,
        provisioning_route=route,
        required_search_anchors=("ch 2H = 2", "exp(4H) = 3"),
    )

    assert verified.extraction_tool == {
        "tool": "stdlib_html_visible_text",
        "version": 1,
        "deterministic": True,
        "arguments": [],
    }
    assert "The Statistics of Honeycomb and Triangular Lattice. I" in verified.extracted_text
    assert "Kodi Husimi and Itiro Syozi" in verified.extracted_text
    assert "ch 2H = 2" in verified.extracted_text
    assert "exp(4H) = 3" in verified.extracted_text
    for hidden in (
        "hidden-css-sentinel",
        "javascript-hidden-sentinel",
        "comment-hidden-sentinel",
        "attribute-hidden-sentinel",
        "hidden-attribute-sentinel",
        "aria-hidden-sentinel",
        "inline-style-hidden-sentinel",
        "noscript-hidden-sentinel",
        "template-hidden-sentinel",
    ):
        assert hidden not in verified.extracted_text


def test_oup_html_accepts_exact_canonical_dotted_doi():
    route_spec = _oup_html_route()
    canonical_payload = OUP_HTML.replace(
        b"https://doi.org/10.1143/ptp.5.2.177",
        b"DOI: 10.1143/PTP.5.2.177",
    )
    assert canonical_payload != OUP_HTML
    assert validate_download_response(
        route_spec,
        status=200,
        headers={"content-type": "text/html"},
        body=canonical_payload,
        final_url=route_spec["url"],
    ) == "text/html"


def _validate_oup_html_payload(payload):
    route_spec = _oup_html_route()
    return validate_download_response(
        route_spec,
        status=200,
        headers={"content-type": "text/html"},
        body=payload,
        final_url=route_spec["url"],
    )


def _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path):
    if validation_mode == "download":
        return _validate_oup_html_payload(payload)
    assert validation_mode == "offline"
    source_dir, source, route = _write_oup_html_source(tmp_path, payload=payload)
    return load_verified_source(
        source_dir,
        expected_source=source,
        provisioning_route=route,
    )


def _oup_html_with_head_meta(payload, name, value):
    marker = b"  </head>"
    assert marker in payload
    return payload.replace(
        marker,
        b'    <meta name="' + name + b'" content="' + value + b'">\n' + marker,
        1,
    )


def _oup_payload_with_inline_doi_style(style, *, extra_doi):
    if extra_doi:
        payload = OUP_HTML.replace(
            b"    </article>",
            b'      <p style="'
            + style
            + b'">'
            + EXTRA_DOI
            + b"</p>\n    </article>",
            1,
        )
    else:
        payload = OUP_HTML.replace(
            b"      <p>" + OUP_RESOLVER + b"</p>",
            b'      <p style="' + style + b'">' + OUP_RESOLVER + b"</p>",
            1,
        )
    assert payload != OUP_HTML
    return payload


def _oup_payload_with_local_stylesheet(stylesheet, *, extra_doi):
    if extra_doi:
        payload = OUP_HTML.replace(
            b"    </article>",
            b'      <p class="hide-doi">'
            + EXTRA_DOI
            + b"</p>\n    </article>",
            1,
        )
    else:
        payload = OUP_HTML.replace(
            b"      <p>" + OUP_RESOLVER + b"</p>",
            b'      <p class="hide-doi">' + OUP_RESOLVER + b"</p>",
            1,
        )
    payload = payload.replace(
        b"</body>",
        b"<style>" + stylesheet + b"</style></body>",
        1,
    )
    assert payload != OUP_HTML
    return payload


def _oup_payload_with_stylesheet_doi_style(
    style,
    *,
    selector_kind,
    extra_doi,
):
    selector = {
        "class": b".hide-doi",
        "id": b"#hide-doi",
        "tag": b"aside",
    }[selector_kind]
    payload = _oup_payload_with_local_stylesheet(
        selector + b" { " + style + b" }",
        extra_doi=extra_doi,
    )
    value = EXTRA_DOI if extra_doi else OUP_RESOLVER
    if selector_kind == "id":
        payload = payload.replace(
            b'<p class="hide-doi">' + value + b"</p>",
            b'<p id="hide-doi">' + value + b"</p>",
            1,
        )
    elif selector_kind == "tag":
        payload = payload.replace(
            b'<p class="hide-doi">' + value + b"</p>",
            b"<aside>" + value + b"</aside>",
            1,
        )
    return payload


@pytest.mark.parametrize(
    "fake_resolver",
    (
        b"evilhttps://doi.org/" + OUP_DOI,
        b"https://evil.invalid/https://doi.org/" + OUP_DOI,
    ),
    ids=("prefixed", "nested"),
)
def test_structured_doi_oup_rejects_fake_visible_resolver(fake_resolver):
    payload = OUP_HTML.replace(OUP_RESOLVER, fake_resolver, 1)
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_oup_html_payload(payload)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("carrier_kind", ("href", "citation-doi", "data-doi"))
@pytest.mark.parametrize(
    "malformed_resolver",
    (
        OUP_RESOLVER + b";",
        OUP_RESOLVER + b"?",
        OUP_RESOLVER + b"#",
        OUP_RESOLVER + b";?",
        OUP_RESOLVER + b";#",
        b"https://doi.org:/" + OUP_DOI,
    ),
    ids=(
        "path-semicolon",
        "empty-query",
        "empty-fragment",
        "semicolon-empty-query",
        "semicolon-empty-fragment",
        "empty-port",
    ),
)
def test_structured_doi_oup_rejects_raw_resolver_syntax_edges(
    tmp_path,
    validation_mode,
    carrier_kind,
    malformed_resolver,
):
    if carrier_kind == "href":
        payload = OUP_HTML.replace(
            b"    </article>",
            b'      <a href="'
            + malformed_resolver
            + b'">Canonical identity</a>\n    </article>',
            1,
        )
    elif carrier_kind == "citation-doi":
        payload = _oup_html_with_head_meta(
            OUP_HTML,
            b"citation_doi",
            malformed_resolver,
        )
    else:
        payload = OUP_HTML.replace(
            b'<article data-private="attribute-hidden-sentinel">',
            b'<article data-private="attribute-hidden-sentinel" data-doi="'
            + malformed_resolver
            + b'">',
            1,
        )
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
def test_structured_doi_oup_rejects_visible_resolver_with_empty_port(
    tmp_path,
    validation_mode,
):
    payload = OUP_HTML.replace(
        OUP_RESOLVER,
        b"https://doi.org:/" + OUP_DOI,
        1,
    )
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize(
    "extra_markup",
    (
        b"<p>Related work " + EXTRA_DOI + b"</p>",
        b"<p>" + EXTRA_DOI + b"</p>",
    ),
    ids=("embedded", "standalone"),
)
def test_structured_doi_oup_rejects_extra_bare_doi(extra_markup):
    payload = OUP_HTML.replace(
        b"    </article>",
        b"      " + extra_markup + b"\n    </article>",
        1,
    )
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_oup_html_payload(payload)


@pytest.mark.parametrize("carrier_kind", ("href", "citation-doi", "data-doi"))
def test_structured_doi_oup_rejects_extra_attribute_carrier(carrier_kind):
    if carrier_kind == "href":
        payload = OUP_HTML.replace(
            b"    </article>",
            b'      <a href="https://doi.org/'
            + EXTRA_DOI
            + b'">Related publication</a>\n    </article>',
            1,
        )
    elif carrier_kind == "citation-doi":
        payload = OUP_HTML.replace(
            b"    </article>",
            b'      <meta name="citation_doi" content="'
            + EXTRA_DOI
            + b'">\n    </article>',
            1,
        )
    else:
        payload = OUP_HTML.replace(
            b'<article data-private="attribute-hidden-sentinel">',
            b'<article data-private="attribute-hidden-sentinel" data-doi="'
            + EXTRA_DOI
            + b'">',
            1,
        )
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_oup_html_payload(payload)


def test_structured_doi_oup_accepts_duplicate_canonical_attribute_carriers():
    payload = OUP_HTML.replace(
        b'<article data-private="attribute-hidden-sentinel">',
        b'<article data-private="attribute-hidden-sentinel" data-doi="DOI: '
        + OUP_DOI.upper()
        + b'">',
        1,
    )
    payload = payload.replace(
        b"    </article>",
        b'      <a href="HTTPS://DOI.ORG:443/'
        + OUP_DOI
        + b'">Canonical identity</a>\n    </article>',
        1,
    )
    assert payload != OUP_HTML
    assert _validate_oup_html_payload(payload) == "text/html"


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    "meta_name",
    (b"citation_doi", b"dc.identifier.doi", b"prism.doi"),
)
def test_structured_doi_oup_head_metadata_can_supply_canonical_identity(
    tmp_path,
    validation_mode,
    meta_name,
):
    payload = OUP_HTML.replace(
        b"      <p>" + OUP_RESOLVER + b"</p>\n",
        b"",
        1,
    )
    payload = _oup_html_with_head_meta(payload, meta_name, OUP_DOI.upper())
    assert payload != OUP_HTML
    _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    "meta_name",
    (b"citation_doi", b"dc.identifier.doi", b"prism.doi"),
)
def test_structured_doi_oup_rejects_extra_head_metadata_doi(
    tmp_path,
    validation_mode,
    meta_name,
):
    payload = _oup_html_with_head_meta(OUP_HTML, meta_name, EXTRA_DOI)
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
def test_structured_doi_oup_ignores_arbitrary_head_metadata_doi(
    tmp_path,
    validation_mode,
):
    payload = _oup_html_with_head_meta(OUP_HTML, b"unrelated.identifier", EXTRA_DOI)
    assert payload != OUP_HTML
    _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
def test_structured_doi_oup_ignores_hidden_body_metadata_doi(
    tmp_path,
    validation_mode,
):
    payload = OUP_HTML.replace(
        b"    </article>",
        b'      <div hidden><meta name="citation_doi" content="'
        + EXTRA_DOI
        + b'"></div>\n    </article>',
        1,
    )
    assert payload != OUP_HTML
    _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize(
    "presentation",
    (
        b"https://doi.org/10.1143/ptp.5.2.17<span>7</span>",
        OUP_DOI,
        b"DOI: " + OUP_DOI + b".",
        b"DOI: " + OUP_DOI + b", verified",
        b"(DOI: " + OUP_DOI + b")",
    ),
    ids=("inline-split", "standalone", "terminal-period", "comma-text", "parenthesized"),
)
def test_structured_doi_oup_accepts_legal_visible_presentation(presentation):
    payload = OUP_HTML.replace(OUP_RESOLVER, presentation, 1)
    assert payload != OUP_HTML
    assert _validate_oup_html_payload(payload) == "text/html"


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    "presentation",
    (
        b"(DOI: " + OUP_DOI + b").",
        b"(" + OUP_RESOLVER + b").",
        b"See (" + OUP_DOI + b").",
    ),
    ids=("parenthesized-label-period", "parenthesized-resolver-period", "prose-period"),
)
def test_structured_doi_oup_accepts_iteratively_trimmed_presentation(
    tmp_path,
    validation_mode,
    presentation,
):
    payload = OUP_HTML.replace(OUP_RESOLVER, presentation, 1)
    assert payload != OUP_HTML
    _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    "surplus_presentation",
    (
        OUP_DOI + b"..",
        OUP_DOI + b",,",
        OUP_DOI + b".,",
        OUP_DOI + b",.",
        OUP_RESOLVER + b"..",
        OUP_RESOLVER + b",,",
        OUP_RESOLVER + b".,",
        OUP_RESOLVER + b",.",
        b"(DOI: " + OUP_DOI + b")..",
        b"(" + OUP_RESOLVER + b")..",
        b"See (" + OUP_DOI + b").,",
        b"((" + OUP_RESOLVER + b")).",
    ),
    ids=(
        "bare-double-period",
        "bare-double-comma",
        "bare-period-comma",
        "bare-comma-period",
        "resolver-double-period",
        "resolver-double-comma",
        "resolver-period-comma",
        "resolver-comma-period",
        "labelled-wrapper-double-period",
        "resolver-wrapper-double-period",
        "prose-wrapper-mixed-punctuation",
        "resolver-double-wrapper",
    ),
)
def test_structured_doi_oup_rejects_surplus_presentation_punctuation(
    tmp_path,
    validation_mode,
    surplus_presentation,
):
    payload = OUP_HTML.replace(OUP_RESOLVER, surplus_presentation, 1)
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    "presentation",
    (
        OUP_DOI + b".",
        OUP_DOI + b", verified",
        OUP_RESOLVER + b".",
        OUP_RESOLVER + b", verified",
        b"(" + OUP_DOI + b").",
    ),
    ids=(
        "bare-period",
        "bare-comma",
        "resolver-period",
        "resolver-comma",
        "bare-wrapper-period",
    ),
)
def test_structured_doi_oup_accepts_single_presentation_layer(
    tmp_path,
    validation_mode,
    presentation,
):
    payload = OUP_HTML.replace(OUP_RESOLVER, presentation, 1)
    assert payload != OUP_HTML
    _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    "prefix",
    (
        b"evil_",
        b"evil-",
        b"evil.",
        b"evil/",
        "é".encode("utf-8"),
        "汉".encode("utf-8"),
        b"evil(",
    ),
    ids=(
        "underscore",
        "hyphen",
        "period",
        "slash",
        "unicode-letter",
        "unicode-cjk",
        "opening-delimiter-without-boundary",
    ),
)
def test_structured_doi_oup_rejects_bare_doi_after_identifier_continuation(
    tmp_path,
    validation_mode,
    prefix,
):
    suffix = b")" if prefix.endswith(b"(") else b""
    payload = OUP_HTML.replace(
        OUP_RESOLVER,
        prefix + OUP_DOI + suffix,
        1,
    )
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    "style",
    (
        b"display:none ! important",
        b"visibility:hidden ! important",
        b"opacity:0",
        b"font-size:0",
        b"content-visibility:hidden",
    ),
    ids=(
        "display-important-whitespace",
        "visibility-important-whitespace",
        "zero-opacity",
        "zero-font-size",
        "hidden-content-visibility",
    ),
)
def test_structured_doi_oup_rejects_inline_style_hidden_sole_doi(
    tmp_path,
    validation_mode,
    style,
):
    payload = OUP_HTML.replace(
        b"      <p>" + OUP_RESOLVER + b"</p>",
        b'      <p style="' + style + b'">' + OUP_RESOLVER + b"</p>",
        1,
    )
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    "style",
    (
        b"display:none ! important",
        b"visibility:hidden ! important",
        b"opacity:0",
        b"font-size:0",
        b"content-visibility:hidden",
    ),
)
def test_structured_doi_oup_ignores_inline_style_hidden_extra_doi(
    tmp_path,
    validation_mode,
    style,
):
    payload = OUP_HTML.replace(
        b"    </article>",
        b'      <p style="'
        + style
        + b'">'
        + EXTRA_DOI
        + b"</p>\n    </article>",
        1,
    )
    assert payload != OUP_HTML
    _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    ("selector", "doi_markup", "declaration"),
    (
        (b".hide-doi", b'<p class="hide-doi">', b"display:none"),
        (b"#hidden-doi", b'<p id="hidden-doi">', b"visibility:hidden"),
        (b"aside", b"<aside>", b"opacity:0"),
    ),
    ids=("class", "id", "tag"),
)
def test_structured_doi_oup_stylesheet_hides_sole_doi_regardless_of_order(
    tmp_path,
    validation_mode,
    selector,
    doi_markup,
    declaration,
):
    closing_tag = b"</aside>" if doi_markup == b"<aside>" else b"</p>"
    payload = OUP_HTML.replace(
        b"      <p>" + OUP_RESOLVER + b"</p>",
        b"      " + doi_markup + OUP_RESOLVER + closing_tag,
        1,
    )
    payload = payload.replace(
        b"</body>",
        b"<style>" + selector + b" { " + declaration + b" }</style></body>",
        1,
    )
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
def test_structured_doi_oup_stylesheet_hidden_extra_doi_does_not_pollute(
    tmp_path,
    validation_mode,
):
    payload = OUP_HTML.replace(
        b"    </article>",
        b'      <p class="hide-doi">'
        + EXTRA_DOI
        + b"</p>\n    </article>",
        1,
    )
    payload = payload.replace(
        b"</body>",
        b"<style>.hide-doi { display:none }</style></body>",
        1,
    )
    _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
def test_structured_doi_oup_ordinary_stylesheet_class_remains_visible(
    tmp_path,
    validation_mode,
):
    payload = OUP_HTML.replace(
        b"      <p>" + OUP_RESOLVER + b"</p>",
        b'      <p class="show-doi">' + OUP_RESOLVER + b"</p>",
        1,
    )
    payload = payload.replace(
        b"</body>",
        b"<style>.show-doi { color: red }</style></body>",
        1,
    )
    _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
def test_oup_stylesheet_prepass_fails_closed_above_character_bound(
    tmp_path,
    monkeypatch,
    validation_mode,
):
    monkeypatch.setattr(
        evidence_sources,
        "_MAX_LOCAL_STYLESHEET_CHARACTERS",
        1,
    )
    with pytest.raises(SourceEvidenceError, match="validation bound"):
        _validate_oup_html_payload_in_mode(OUP_HTML, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
def test_round5_oup_stylesheet_comments_count_before_character_bound(
    tmp_path,
    monkeypatch,
    validation_mode,
):
    monkeypatch.setattr(
        evidence_sources,
        "_MAX_LOCAL_STYLESHEET_CHARACTERS",
        16,
    )
    payload = _oup_payload_with_local_stylesheet(
        b"/*" + (b"x" * 32) + b"*/ .hide-doi { opacity:1 }",
        extra_doi=False,
    )
    with pytest.raises(SourceEvidenceError, match="validation bound"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("style", ROUND5_HIDDEN_ZERO_AND_FUNCTION_STYLES)
def test_round5_oup_zero_and_ambiguous_function_styles_hide_doi(
    tmp_path,
    validation_mode,
    style,
    extra_doi,
):
    payload = _oup_payload_with_inline_doi_style(style, extra_doi=extra_doi)
    if extra_doi:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize(
    ("selector_kind", "declaration"),
    (
        ("class", b"opacity:+0"),
        ("id", b"font-size:calc(0px)"),
        ("tag", b"display:var(--display)"),
    ),
    ids=("class-zero", "id-calc-zero", "tag-ambiguous-function"),
)
def test_round5_oup_simple_stylesheet_selectors_apply_hidden_values(
    tmp_path,
    validation_mode,
    selector_kind,
    declaration,
    extra_doi,
):
    selector = {
        "class": b".hide-doi",
        "id": b"#hide-doi",
        "tag": b"aside",
    }[selector_kind]
    payload = _oup_payload_with_local_stylesheet(
        selector + b" { " + declaration + b" }",
        extra_doi=extra_doi,
    )
    value = EXTRA_DOI if extra_doi else OUP_RESOLVER
    if selector_kind == "id":
        payload = payload.replace(
            b'<p class="hide-doi">' + value + b"</p>",
            b'<p id="hide-doi">' + value + b"</p>",
            1,
        )
    elif selector_kind == "tag":
        payload = payload.replace(
            b'<p class="hide-doi">' + value + b"</p>",
            b"<aside>" + value + b"</aside>",
            1,
        )
    if extra_doi:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("style", ROUND5_VISIBLE_STYLE_CONTROLS)
def test_round5_oup_nonzero_and_ordinary_styles_remain_visible(
    tmp_path,
    validation_mode,
    style,
    extra_doi,
):
    payload = _oup_payload_with_inline_doi_style(style, extra_doi=extra_doi)
    if extra_doi:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("style", ROUND6_I1_HIDDEN_STYLES)
def test_round6_i1_oup_clamped_and_unreliable_inline_values_hide_doi(
    tmp_path,
    validation_mode,
    style,
    extra_doi,
):
    payload = _oup_payload_with_inline_doi_style(style, extra_doi=extra_doi)
    if extra_doi:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize(
    ("selector_kind", "style"),
    ROUND6_I1_STYLESHEET_CASES,
)
def test_round6_i1_oup_clamped_and_unreliable_stylesheet_values_hide_doi(
    tmp_path,
    validation_mode,
    selector_kind,
    style,
    extra_doi,
):
    payload = _oup_payload_with_stylesheet_doi_style(
        style,
        selector_kind=selector_kind,
        extra_doi=extra_doi,
    )
    if extra_doi:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("style", ROUND6_I1_VISIBLE_STYLES)
def test_round6_i1_oup_reliable_positive_and_negative_font_controls_visible(
    tmp_path,
    validation_mode,
    style,
    extra_doi,
):
    payload = _oup_payload_with_inline_doi_style(style, extra_doi=extra_doi)
    if extra_doi:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize(
    ("selector_kind", "style"),
    ROUND6_I1_VISIBLE_STYLESHEET_CASES,
)
def test_round6_i1_oup_reliable_stylesheet_controls_remain_visible(
    tmp_path,
    validation_mode,
    selector_kind,
    style,
    extra_doi,
):
    payload = _oup_payload_with_stylesheet_doi_style(
        style,
        selector_kind=selector_kind,
        extra_doi=extra_doi,
    )
    if extra_doi:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("style", ROUND6_COLLAPSED_VISIBILITY_STYLES)
def test_round6_i2_oup_collapsed_inline_visibility_hides_doi(
    tmp_path,
    validation_mode,
    style,
    extra_doi,
):
    payload = _oup_payload_with_inline_doi_style(style, extra_doi=extra_doi)
    if extra_doi:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("selector_kind", ("class", "id", "tag"))
@pytest.mark.parametrize("style", ROUND6_COLLAPSED_VISIBILITY_STYLES)
def test_round6_i2_oup_collapsed_stylesheet_visibility_hides_doi(
    tmp_path,
    validation_mode,
    style,
    selector_kind,
    extra_doi,
):
    payload = _oup_payload_with_stylesheet_doi_style(
        style,
        selector_kind=selector_kind,
        extra_doi=extra_doi,
    )
    if extra_doi:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("style", ROUND6_VISIBLE_VISIBILITY_STYLES)
def test_round6_i2_oup_ordinary_inline_visibility_remains_visible(
    tmp_path,
    validation_mode,
    style,
    extra_doi,
):
    payload = _oup_payload_with_inline_doi_style(style, extra_doi=extra_doi)
    if extra_doi:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize(
    ("selector_kind", "style"),
    (
        ("class", b"visibility:visible"),
        ("id", b"visibility:inherit"),
        ("tag", b"visibility:initial"),
    ),
    ids=("class-visible", "id-inherit", "tag-initial"),
)
def test_round6_i2_oup_ordinary_stylesheet_visibility_remains_visible(
    tmp_path,
    validation_mode,
    selector_kind,
    style,
    extra_doi,
):
    payload = _oup_payload_with_stylesheet_doi_style(
        style,
        selector_kind=selector_kind,
        extra_doi=extra_doi,
    )
    if extra_doi:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("style", ROUND5_COMMENT_HIDDEN_STYLES)
def test_round5_oup_inline_css_comments_preserve_hidden_declarations(
    tmp_path,
    validation_mode,
    style,
    extra_doi,
):
    payload = _oup_payload_with_inline_doi_style(style, extra_doi=extra_doi)
    if extra_doi:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
def test_round5_oup_unterminated_inline_css_comment_hides_fail_closed(
    tmp_path,
    validation_mode,
    extra_doi,
):
    payload = _oup_payload_with_inline_doi_style(
        b"display:/*unterminated",
        extra_doi=extra_doi,
    )
    if extra_doi:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
def test_round5_oup_overlimit_inline_css_hides_fail_closed(
    tmp_path,
    monkeypatch,
    validation_mode,
    extra_doi,
):
    monkeypatch.setattr(
        evidence_sources,
        "_MAX_INLINE_STYLE_CHARACTERS",
        8,
        raising=False,
    )
    payload = _oup_payload_with_inline_doi_style(
        b"display:block;opacity:1",
        extra_doi=extra_doi,
    )
    if extra_doi:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("at_rule", ROUND5_STATEMENT_AT_RULES)
def test_round5_oup_statement_at_rule_does_not_swallow_hidden_rule(
    tmp_path,
    validation_mode,
    at_rule,
    extra_doi,
):
    stylesheet = at_rule + b"\n.hide-doi { display:none }"
    payload = _oup_payload_with_local_stylesheet(
        stylesheet,
        extra_doi=extra_doi,
    )
    if extra_doi:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("unsupported_rule", ROUND5_UNSUPPORTED_PREFIX_RULES)
def test_round5_oup_unsupported_selector_does_not_swallow_hidden_rule(
    tmp_path,
    validation_mode,
    unsupported_rule,
    extra_doi,
):
    stylesheet = unsupported_rule + b"\n.hide-doi { display:none }"
    payload = _oup_payload_with_local_stylesheet(
        stylesheet,
        extra_doi=extra_doi,
    )
    if extra_doi:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
def test_round5_oup_cdo_cdc_wrapper_preserves_hidden_rule(
    tmp_path,
    validation_mode,
    extra_doi,
):
    payload = _oup_payload_with_local_stylesheet(
        b"<!--\n.hide-doi { display:none }\n-->",
        extra_doi=extra_doi,
    )
    if extra_doi:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
@pytest.mark.parametrize("at_rule", ROUND5_STATEMENT_AT_RULES)
def test_round5_oup_statement_at_rule_preserves_visible_control(
    tmp_path,
    validation_mode,
    at_rule,
    extra_doi,
):
    stylesheet = at_rule + b"\n.hide-doi { opacity:1 }"
    payload = _oup_payload_with_local_stylesheet(
        stylesheet,
        extra_doi=extra_doi,
    )
    if extra_doi:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    "ambiguous_stylesheet",
    (
        b"@media screen { .hide-doi { opacity:1 } }",
        b"orphan-token; .hide-doi { opacity:1 }",
        b"/* unterminated",
        b'@import url("unterminated); .hide-doi { display:none }',
    ),
    ids=(
        "unsupported-block-at-rule",
        "ambiguous-residual-statement",
        "unterminated-comment",
        "unterminated-at-rule-string-paren",
    ),
)
def test_round5_oup_ambiguous_stylesheet_fails_closed(
    tmp_path,
    validation_mode,
    ambiguous_stylesheet,
):
    payload = _oup_payload_with_local_stylesheet(
        ambiguous_stylesheet,
        extra_doi=False,
    )
    with pytest.raises(SourceEvidenceError, match="style|CSS|validation"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
def test_round5_oup_statement_at_rules_count_toward_stylesheet_bound(
    tmp_path,
    monkeypatch,
    validation_mode,
):
    monkeypatch.setattr(
        evidence_sources,
        "_MAX_LOCAL_STYLESHEET_RULES",
        1,
    )
    payload = _oup_payload_with_local_stylesheet(
        b"@layer one; @layer two; .hide-doi { opacity:1 }",
        extra_doi=False,
    )
    with pytest.raises(SourceEvidenceError, match="too many"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


def test_structured_doi_oup_accepts_duplicate_canonical_plain_value():
    payload = OUP_HTML.replace(
        b"    </article>",
        b"      <p>" + OUP_DOI.upper() + b"</p>\n    </article>",
        1,
    )
    assert payload != OUP_HTML
    assert _validate_oup_html_payload(payload) == "text/html"


@pytest.mark.parametrize("suffix", (b".999", b"/999", b"-other", b"_other"))
def test_oup_html_rejects_longer_doi_with_canonical_prefix(suffix):
    route_spec = _oup_html_route()
    longer_doi_payload = OUP_HTML.replace(
        b"10.1143/ptp.5.2.177",
        b"10.1143/ptp.5.2.177" + suffix,
    )
    with pytest.raises(SourceEvidenceError, match="DOI"):
        validate_download_response(
            route_spec,
            status=200,
            headers={"content-type": "text/html"},
            body=longer_doi_payload,
            final_url=route_spec["url"],
        )


def test_oup_html_rejects_slash_substitute_for_canonical_doi():
    route_spec = _oup_html_route()
    slash_substitute = OUP_HTML.replace(
        b"10.1143/ptp.5.2.177",
        b"10.1143/ptp/5.2.177",
    )
    with pytest.raises(SourceEvidenceError, match="DOI"):
        validate_download_response(
            route_spec,
            status=200,
            headers={"content-type": "text/html"},
            body=slash_substitute,
            final_url=route_spec["url"],
        )


@pytest.mark.parametrize(
    "payload",
    (
        b"<html><head><article>"
        b"The Statistics of Honeycomb and Triangular Lattice. I; "
        b"Kodi Husimi and Itiro Syozi; 10.1143/ptp.5.2.177; Summary; "
        b"ch 2H = 2; exp(4H) = 3"
        b"</article></head></html>",
        b"<html><head></head><main>"
        b"The Statistics of Honeycomb and Triangular Lattice. I; "
        b"Kodi Husimi and Itiro Syozi; 10.1143/ptp.5.2.177; Summary; "
        b"ch 2H = 2; exp(4H) = 3"
        b"</main><body></body></html>",
        b"<html><head><div class='minimal-article-container'>"
        b"The Statistics of Honeycomb and Triangular Lattice. I; "
        b"Kodi Husimi and Itiro Syozi; 10.1143/ptp.5.2.177; Summary; "
        b"ch 2H = 2; exp(4H) = 3"
        b"</div></head><body></body></html>",
    ),
)
def test_html_article_bearing_content_must_be_inside_complete_body(payload):
    route_spec = _oup_html_route()
    with pytest.raises(SourceEvidenceError, match="body"):
        validate_download_response(
            route_spec,
            status=200,
            headers={"content-type": "text/html"},
            body=payload,
            final_url=route_spec["url"],
        )


@pytest.mark.parametrize(
    ("old", "new", "match"),
    (
        (
            b"The Statistics of Honeycomb and Triangular Lattice. I",
            b"A different article title",
            "title",
        ),
        (b"10.1143/ptp.5.2.177", b"10.1143/wrong", "DOI"),
        (b"Kodi Husimi", b"Unknown Author", "author"),
        (b"Summary", b"Overview unavailable", "summary"),
        (b"ch 2H = 2", b"first condition unavailable", "equation"),
        (b"exp(4H) = 3", b"second condition unavailable", "equation"),
    ),
)
def test_oup_offline_loader_automatically_replays_route_anchors(
    tmp_path, old, new, match
):
    payload = OUP_HTML.replace(old, new)
    source_dir, source, route = _write_oup_html_source(tmp_path, payload=payload)
    with pytest.raises(SourceEvidenceError, match=match):
        load_verified_source(
            source_dir,
            expected_source=source,
            provisioning_route=route,
        )


def test_oup_minimal_div_container_is_article_bearing_for_download_and_offline(
    tmp_path,
):
    route_spec = _oup_html_route()
    assert validate_download_response(
        route_spec,
        status=200,
        headers={"content-type": "text/html; charset=UTF-8"},
        body=OUP_MINIMAL_DIV_HTML,
        final_url=route_spec["url"],
    ) == "text/html"

    source_dir, source, route = _write_oup_html_source(
        tmp_path, payload=OUP_MINIMAL_DIV_HTML
    )
    verified = load_verified_source(
        source_dir,
        expected_source=source,
        provisioning_route=route,
        required_search_anchors=("ch 2H = 2", "exp (4H) = 3"),
    )
    assert "The Statistics of Honeycomb and Triangular Lattice. I" in (
        verified.extracted_text
    )
    assert "Kodi Husimi and Itiro Syôzi" in verified.extracted_text


def test_fetcher_records_exact_deterministic_html_extraction_contract():
    route_spec = _oup_html_route()
    source = {
        "source_id": "doi_f334ed253565110358b3",
        "canonical_identity": {"kind": "doi", "value": "10.1143/ptp.5.2.177"},
        "canonical_url": "https://doi.org/10.1143/ptp.5.2.177",
    }
    route = {"authoritative_retrieval_route": route_spec}
    response = {
        "body": OUP_HTML,
        "final_url": route_spec["url"],
        "status": 200,
        "headers": {"Content-Type": "text/html"},
        "media_type": "text/html",
    }
    provenance = source_fetcher._build_provenance(
        source,
        route,
        response,
        {
            "title": "The Statistics of Honeycomb and Triangular Lattice. I",
            "authors": ["Kodi Husimi", "Itiro Syozi"],
            "venue": "Progress of Theoretical Physics",
            "publication_date": "1950-03-01",
        },
        payload_name="source.html",
    )
    assert provenance["text_extraction"] == {
        "tool": "stdlib_html_visible_text",
        "version": 1,
        "deterministic": True,
        "arguments": [],
    }


@pytest.mark.parametrize(
    ("status", "content_type", "body", "match"),
    [
        (503, "text/html", OUP_HTML, "HTTP status"),
        (200, "application/pdf", OUP_HTML, "media type"),
        (
            200,
            "text/html",
            b"<html><body><article>Access denied: verify you are human with Cloudflare.</article></body></html>",
            "challenge",
        ),
        (200, "text/html", OUP_HTML.replace(b"<html lang=\"en\">", b""), "root"),
        (200, "text/html", OUP_HTML.replace(b"</article>", b""), "malformed"),
        (
            200,
            "text/html",
            b"<html><body><article><script>"
            b"The Statistics of Honeycomb and Triangular Lattice. I; "
            b"Kodi Husimi and Itiro Syozi; 10.1143/ptp.5.2.177; Summary; "
            b"ch 2H = 2; exp(4H) = 3"
            b"</script><p>Visible shell.</p></article></body></html>",
            "title",
        ),
        (200, "text/html", b"<html><body><article>   </article></body></html>", "article"),
        (200, "text/html", OUP_HTML.replace(b"The Statistics of Honeycomb and Triangular Lattice. I", b"Different title"), "title"),
        (200, "text/html", OUP_HTML.replace(b"10.1143/ptp.5.2.177", b"10.1143/wrong"), "DOI"),
        (200, "text/html", OUP_HTML.replace(b"Kodi Husimi", b"Unknown Author"), "author"),
        (200, "text/html", OUP_HTML.replace(b"ch 2H = 2", b"condition unavailable"), "equation"),
        (200, "text/html", OUP_HTML.replace(b"exp(4H) = 3", b"condition unavailable"), "equation"),
    ],
)
def test_html_download_fails_closed(status, content_type, body, match):
    route_spec = _oup_html_route()
    with pytest.raises(SourceEvidenceError, match=match):
        validate_download_response(
            route_spec,
            status=status,
            headers={"content-type": content_type},
            body=body,
            final_url=route_spec["url"],
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
