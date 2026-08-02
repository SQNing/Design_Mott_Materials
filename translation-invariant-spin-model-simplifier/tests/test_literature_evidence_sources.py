from collections import Counter
import copy
import hashlib
import json
import os
import random
import re
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote_plus, unquote_plus, urlencode
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
OUP_DOI = b"10.1143/ptp/5.2.177"
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
    <article class="minimal-article-container" data-private="attribute-hidden-sentinel">
      <header class="article-header">
        <h1>The Statistics of Honeycomb and Triangular Lattice. I</h1>
        <p class="authors">Kodi Husimi and Itiro Sy&#244;zi</p>
        <p>Volume 5, Issue 2, March 1950, Pages 177-186</p>
        <div class="ww-citation-primary">
          <a href="https://doi.org/10.1143/ptp/5.2.177"><p>https://doi.org/10.1143/ptp/5.2.177</p></a>
        </div>
      </header>
      <section class="article-content"><h2>Summary</h2>
        <p>We applied the matrix method to the honeycomb lattice and obtained
        its exact solution and the triangular-net dual.</p>
        <p>The Curie point occurs at ch 2H = 2 in the honeycomb lattice and at
        exp(4H) = 3 in the triangular net.</p>
        <div class="ref-list"><a href="https://doi.org/10.1000/cited-work">10.1000/cited-work</a></div>
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
        <p>Volume 5, Issue 2, March 1950, Pages 177-186</p>
        <div class="ww-citation-primary"><a href="https://doi.org/10.1143/ptp/5.2.177"><p>https://doi.org/10.1143/ptp/5.2.177</p></a></div>
      </div>
      <div class="article-content">
        <h2>Summary</h2>
        <section class="abstract">
          <p>The Curie point occurs at ch 2H = 2 in the honeycomb lattice and
          at exp (4H) = 3 in the triangular net.</p>
          <div class="ref-list"><a href="https://doi.org/10.1000/cited-work">10.1000/cited-work</a></div>
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
        "payload_relative_path": "source.xml",
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
        "local_cache_location": f"source-cache/{SOURCE_ID}/source.xml",
        "current_availability": "not_acquired",
    }


def _write_source(tmp_path, provenance=None, payload=PAYLOAD):
    source_dir = tmp_path / SOURCE_ID
    source_dir.mkdir(parents=True)
    source_dir.joinpath("source.xml").write_bytes(payload)
    source_dir.joinpath("provenance.json").write_text(
        json.dumps(provenance or _provenance(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return source_dir


@pytest.mark.parametrize(
    "relative_path",
    (
        pytest.param("../source.xml", id="parent-traversal"),
        pytest.param("nested/source.xml", id="nested-subdirectory"),
        pytest.param("/source.xml", id="absolute-path"),
        pytest.param(".", id="dot"),
        pytest.param("..", id="dotdot"),
    ),
)
def test_payload_path_rejects_every_nonlocal_filename(tmp_path, relative_path):
    with pytest.raises(
        SourceEvidenceError,
        match=r"^payload_relative_path must name one local payload file$",
    ):
        evidence_sources._payload_path(tmp_path, relative_path)


@pytest.mark.parametrize(
    "relative_path",
    (
        pytest.param("", id="empty"),
        pytest.param("   ", id="whitespace"),
        pytest.param(None, id="none"),
        pytest.param(17, id="integer"),
        pytest.param(["source.xml"], id="list"),
    ),
)
def test_payload_path_rejects_nontext_or_empty_filename(tmp_path, relative_path):
    with pytest.raises(
        SourceEvidenceError,
        match=r"^payload_relative_path must be nonempty text$",
    ):
        evidence_sources._payload_path(tmp_path, relative_path)


def test_payload_path_accepts_canonical_single_local_filename(tmp_path):
    assert evidence_sources._payload_path(tmp_path, "source.xml") == (
        tmp_path / "source.xml"
    )


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
    source_dir.joinpath("source.xml").write_bytes(PAYLOAD + b"mutated")
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
    provenance["payload_relative_path"] = "source.pdf"
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
    provisioning["local_cache_location"] = f"source-cache/{SOURCE_ID}/source.pdf"
    source_dir = _write_source(tmp_path, provenance=provenance, payload=payload)
    source_dir.joinpath("source.xml").rename(source_dir / "source.pdf")

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
    provenance["payload_relative_path"] = "source.pdf"
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
    provisioning["local_cache_location"] = f"source-cache/{SOURCE_ID}/source.pdf"
    source_dir = _write_source(tmp_path, provenance=provenance, payload=payload)
    source_dir.joinpath("source.xml").rename(source_dir / "source.pdf")

    with pytest.raises(SourceEvidenceError, match="pdftotext version"):
        load_verified_source(
            source_dir,
            expected_source=_expected_source(),
            provisioning_route=provisioning,
            required_search_anchors=("target observable",),
        )


def _canonical_payload_loader_fixture(tmp_path, media_type):
    if media_type == "application/xml":
        return _write_source(tmp_path), _expected_source(), _provisioning()
    if media_type == "text/html":
        return _write_oup_html_source(tmp_path)
    assert media_type == "application/pdf"
    payload = _minimal_pdf("Canonical PDF payload for exact filename validation.")
    provenance = _provenance(payload)
    provenance["media_type"] = "application/pdf"
    provenance["payload_relative_path"] = "source.pdf"
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
    provisioning["local_cache_location"] = f"source-cache/{SOURCE_ID}/source.pdf"
    source_dir = _write_source(tmp_path, provenance=provenance, payload=payload)
    source_dir.joinpath("source.xml").rename(source_dir / "source.pdf")
    return source_dir, _expected_source(), provisioning


@pytest.mark.parametrize(
    "media_type",
    ["application/pdf", "application/xml", "text/html"],
)
def test_loader_accepts_exact_canonical_payload_filename(tmp_path, media_type):
    source_dir, source, provisioning = _canonical_payload_loader_fixture(
        tmp_path, media_type
    )

    verified = load_verified_source(
        source_dir,
        expected_source=source,
        provisioning_route=provisioning,
    )

    extension = evidence_sources.payload_extension_for_media_type(media_type)
    assert verified.payload_path.name == f"source.{extension}"


_CANONICAL_PAYLOAD_MUTATIONS = (
    "wrong_same_extension_basename",
    "upper_or_mixed_extension",
    "wrong_extension",
    "empty",
    "none",
    "media_and_filename",
)


def _mutated_media_and_filename(media_type, mutation):
    extensions = {
        "application/pdf": "pdf",
        "application/xml": "xml",
        "text/html": "html",
    }
    extension = extensions[media_type]
    if mutation == "wrong_same_extension_basename":
        return media_type, f"payload.{extension}"
    if mutation == "upper_or_mixed_extension":
        return media_type, f"source.{extension.upper()}"
    if mutation == "wrong_extension":
        wrong_extension = {"pdf": "xml", "xml": "html", "html": "pdf"}[extension]
        return media_type, f"source.{wrong_extension}"
    if mutation == "empty":
        return media_type, ""
    if mutation == "none":
        return media_type, None
    assert mutation == "media_and_filename"
    wrong_media = {
        "application/pdf": "application/xml",
        "application/xml": "text/html",
        "text/html": "application/pdf",
    }[media_type]
    return wrong_media, f"payload.{extensions[wrong_media]}"


@pytest.mark.parametrize(
    "media_type",
    ["application/pdf", "application/xml", "text/html"],
)
@pytest.mark.parametrize("mutation", _CANONICAL_PAYLOAD_MUTATIONS)
def test_loader_rejects_every_noncanonical_provenance_payload_filename_before_read(
    tmp_path, media_type, mutation
):
    source_dir, source, provisioning = _canonical_payload_loader_fixture(
        tmp_path, media_type
    )
    provenance_path = source_dir / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    original_name = provenance["payload_relative_path"]
    mutated_media, mutated_name = _mutated_media_and_filename(media_type, mutation)
    provenance["media_type"] = mutated_media
    provenance["payload_relative_path"] = mutated_name
    if isinstance(mutated_name, str) and mutated_name:
        source_dir.joinpath(original_name).rename(source_dir / mutated_name)
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        SourceEvidenceError,
        match="canonical payload filename|payload media type disagrees",
    ):
        load_verified_source(
            source_dir,
            expected_source=source,
            provisioning_route=provisioning,
        )


@pytest.mark.parametrize(
    "media_type",
    ["application/pdf", "application/xml", "text/html"],
)
@pytest.mark.parametrize("mutation", _CANONICAL_PAYLOAD_MUTATIONS)
def test_loader_rejects_every_noncanonical_provisioning_payload_location_before_read(
    tmp_path, media_type, mutation
):
    source_dir, source, provisioning = _canonical_payload_loader_fixture(
        tmp_path, media_type
    )
    source_id = provisioning["source_id"]
    mutated_media, mutated_name = _mutated_media_and_filename(media_type, mutation)
    provisioning["expected_media_type"] = mutated_media
    provisioning["local_cache_location"] = (
        f"source-cache/{source_id}/{mutated_name}"
        if isinstance(mutated_name, str) and mutated_name
        else mutated_name
    )

    with pytest.raises(
        SourceEvidenceError,
        match="canonical payload cache location|payload media type disagrees",
    ):
        load_verified_source(
            source_dir,
            expected_source=source,
            provisioning_route=provisioning,
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
            "doi:10.1143/ptp/5.2.177",
            {
                "kind": "oup_minimal_html",
                "url": "https://oup.silverchair-cdn.com/article-minimal/1942776",
                "expected_media_type": "text/html",
                "access_mode": "unattended",
                "artifact_identifier": "oup-silverchair-article-minimal:1942776",
                "work_identity_evidence": {
                    "kind": "crossref_oup_same_work",
                    "url": "https://api.crossref.org/works/10.1143%2Fptp%2F5.2.177",
                },
            },
        ),
        (
            "doi:10.1088/0305-4470/17/13/020",
            {
                "kind": "institutional_repository_pdf",
                "url": "https://core.ac.uk/download/572184419.pdf",
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
                    "kind": "hal_same_work_bibliographic_payload",
                    "url": "https://api.archives-ouvertes.fr/search/",
                    "record_identifier": "hal-02340631v1",
                    "stable_document_url": "https://hal.science/hal-02340631v1",
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
    "title": "The Majumdar-Ghosh chain:Twofold ground state and elementary excitations",
    "authors": ["W. J. Caspers", "K. M. Emmett", "W. Magnus"],
}


def _core_mg_work_identity_document():
    return {
        "id": 572184419,
        "doi": "10.1088/0305-4470/17/13/020",
        "title": "The Majumdar-Ghosh chain:Twofold ground state and elementary excitations",
        "fulltextStatus": "enabled",
        "authors": [
            {"name": "Caspers, W.J."},
            {"name": "Emmett, K.M."},
            {"name": "Magnus, W."},
        ],
        "downloadUrl": "https://core.ac.uk/download/572184419.pdf",
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
    ("doi", "output_id", "title", "fulltext_status", "authors", "pdf_location"),
)
def test_core_same_work_output_rejects_each_independent_mismatch(perturbation):
    document = _core_mg_work_identity_document()
    if perturbation == "doi":
        document["doi"] = "10.1088/0305-4470/17/13/999"
    elif perturbation == "output_id":
        document["id"] = 572184418
    elif perturbation == "title":
        document["title"] = "A different spin-chain paper"
    elif perturbation == "fulltext_status":
        document["fulltextStatus"] = "disabled"
    elif perturbation == "authors":
        document["authors"][-1] = {"name": "A Different Author"}
    else:
        document["downloadUrl"] = "https://core.ac.uk/download/572184418.pdf"

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
    pytest.param(b'@charset "UTF-8";', id="charset-with-quoted-string"),
)
ROUND5_UNSUPPORTED_PREFIX_RULES = (
    pytest.param(
        b".complex > .unused { color:red }",
        id="complex-selector",
    ),
    pytest.param(
        b".escaped\\2d selector { color:red }",
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
    # The author-page parser remains a generic non-regression surface, but the
    # corrected Garel route below must no longer select it.
    return {
        "kind": "author_repository_pdf",
        "url": (
            "https://www.lptmc.jussieu.fr/files/maillard/PUB2/"
            "Frustrated_jav16i10p2257.pdf"
        ),
        "expected_media_type": "application/pdf",
        "access_mode": "unattended",
        "artifact_identifier": "author-repository:Frustrated_jav16i10p2257.pdf",
        "work_identity_evidence": {
            "kind": "author_publications_same_work",
            "url": "https://www.lptmc.jussieu.fr/users/maillard",
        },
    }


def _task5a_garel_route():
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


def _special_sidecar_cache(tmp_path, evidence_kind, *, write_sidecar=True):
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
        "local_cache_location": f"source-cache/{source_id}/source.pdf",
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
    if write_sidecar:
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


@pytest.mark.parametrize(
    "media_type",
    ["text/plain", "Application/Pdf", "TEXT/HTML", "", None],
)
def test_payload_extension_mapping_rejects_every_unknown_media_type(media_type):
    with pytest.raises(SourceEvidenceError, match="unsupported.*media type"):
        evidence_sources.payload_extension_for_media_type(media_type)


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


def test_round7_d_main_stdout_stderr_drop_secret_case_variants_and_internal_profile(
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


def test_round7_d_provenance_omits_case_insensitive_header_reflections(monkeypatch):
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
        sensitive_values=(MIXED_CASE_CREDENTIAL_SENTINEL,),
    )
    assert MIXED_CASE_CREDENTIAL_SENTINEL.casefold() not in (
        json.dumps(provenance, sort_keys=True).casefold()
    )


def test_round7_d_provenance_rejects_active_credential_in_serialized_final_path(
    monkeypatch,
):
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
            sensitive_values=(MIXED_CASE_CREDENTIAL_SENTINEL,),
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
        {"kind": "doi", "value": "10.1143/ptp/5.2.177"}
    )


def _write_oup_html_source(tmp_path, payload=OUP_HTML):
    source_id = "doi_457c49167653440059e9"
    route_spec = _oup_html_route()
    source = {
        "source_id": source_id,
        "canonical_identity": {"kind": "doi", "value": "10.1143/ptp/5.2.177"},
        "canonical_url": "https://doi.org/10.1143/ptp/5.2.177",
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
        "local_cache_location": f"source-cache/{source_id}/source.html",
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
                "version": 2,
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
        "version": 2,
        "deterministic": True,
        "arguments": [],
    }
    assert "The Statistics of Honeycomb and Triangular Lattice. I" in verified.extracted_text
    assert "Kodi Husimi and Itiro Syôzi" in verified.extracted_text
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


def test_oup_html_accepts_exact_canonical_slash_doi_anchor_href_and_text():
    route_spec = _oup_html_route()
    assert validate_download_response(
        route_spec,
        status=200,
        headers={"content-type": "text/html"},
        body=OUP_HTML,
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
            b'<article class="minimal-article-container" data-private="attribute-hidden-sentinel">',
            b'<article class="minimal-article-container" data-private="attribute-hidden-sentinel" data-doi="'
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
            b'<article class="minimal-article-container" data-private="attribute-hidden-sentinel">',
            b'<article class="minimal-article-container" data-private="attribute-hidden-sentinel" data-doi="'
            + EXTRA_DOI
            + b'">',
            1,
        )
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI"):
        _validate_oup_html_payload(payload)


def test_structured_doi_oup_rejects_duplicate_canonical_attribute_carriers():
    payload = OUP_HTML.replace(
        b'<article class="minimal-article-container" data-private="attribute-hidden-sentinel">',
        b'<article class="minimal-article-container" data-private="attribute-hidden-sentinel" data-doi="DOI: '
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
    with pytest.raises(SourceEvidenceError, match="DOI|carrier"):
        _validate_oup_html_payload(payload)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    "meta_name",
    (b"citation_doi", b"dc.identifier.doi", b"prism.doi"),
)
def test_structured_doi_oup_head_metadata_cannot_supply_canonical_identity(
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
    with pytest.raises(SourceEvidenceError, match="DOI|anchor"):
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
def test_structured_doi_oup_rejects_arbitrary_head_metadata_doi_outside_ref_list(
    tmp_path,
    validation_mode,
):
    payload = _oup_html_with_head_meta(OUP_HTML, b"unrelated.identifier", EXTRA_DOI)
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI|carrier"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
def test_structured_doi_oup_rejects_hidden_body_metadata_doi_outside_ref_list(
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
    with pytest.raises(SourceEvidenceError, match="DOI|carrier"):
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
def test_structured_doi_oup_rejects_nonexact_visible_identity_presentation(presentation):
    payload = OUP_HTML.replace(OUP_RESOLVER, presentation, 1)
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI|anchor"):
        _validate_oup_html_payload(payload)


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
def test_structured_doi_oup_rejects_iteratively_trimmed_identity_presentation(
    tmp_path,
    validation_mode,
    presentation,
):
    payload = OUP_HTML.replace(OUP_RESOLVER, presentation, 1)
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI|anchor"):
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
def test_structured_doi_oup_rejects_single_nonexact_presentation_layer(
    tmp_path,
    validation_mode,
    presentation,
):
    payload = OUP_HTML.replace(OUP_RESOLVER, presentation, 1)
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI|anchor"):
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


def test_structured_doi_oup_rejects_duplicate_canonical_plain_value():
    payload = OUP_HTML.replace(
        b"    </article>",
        b"      <p>" + OUP_DOI.upper() + b"</p>\n    </article>",
        1,
    )
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI|carrier"):
        _validate_oup_html_payload(payload)


@pytest.mark.parametrize("suffix", (b".999", b"/999", b"-other", b"_other"))
def test_oup_html_rejects_longer_doi_with_canonical_prefix(suffix):
    route_spec = _oup_html_route()
    longer_doi_payload = OUP_HTML.replace(
        b"10.1143/ptp/5.2.177",
        b"10.1143/ptp/5.2.177" + suffix,
    )
    with pytest.raises(SourceEvidenceError, match="DOI"):
        validate_download_response(
            route_spec,
            status=200,
            headers={"content-type": "text/html"},
            body=longer_doi_payload,
            final_url=route_spec["url"],
        )


def test_oup_html_rejects_dotted_hybrid_substitute_for_canonical_doi():
    route_spec = _oup_html_route()
    dotted_substitute = OUP_HTML.replace(
        b"10.1143/ptp/5.2.177",
        b"10.1143/ptp.5.2.177",
    )
    with pytest.raises(SourceEvidenceError, match="DOI"):
        validate_download_response(
            route_spec,
            status=200,
            headers={"content-type": "text/html"},
            body=dotted_substitute,
            final_url=route_spec["url"],
        )


@pytest.mark.parametrize(
    "payload",
    (
        b"<html><head><article>"
        b"The Statistics of Honeycomb and Triangular Lattice. I; "
        b"Kodi Husimi and Itiro Syozi; 10.1143/ptp/5.2.177; Summary; "
        b"ch 2H = 2; exp(4H) = 3"
        b"</article></head></html>",
        b"<html><head></head><main>"
        b"The Statistics of Honeycomb and Triangular Lattice. I; "
        b"Kodi Husimi and Itiro Syozi; 10.1143/ptp/5.2.177; Summary; "
        b"ch 2H = 2; exp(4H) = 3"
        b"</main><body></body></html>",
        b"<html><head><div class='minimal-article-container'>"
        b"The Statistics of Honeycomb and Triangular Lattice. I; "
        b"Kodi Husimi and Itiro Syozi; 10.1143/ptp/5.2.177; Summary; "
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
        (b"10.1143/ptp/5.2.177", b"10.1143/wrong", "DOI"),
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
        "source_id": "doi_457c49167653440059e9",
        "canonical_identity": {"kind": "doi", "value": "10.1143/ptp/5.2.177"},
        "canonical_url": "https://doi.org/10.1143/ptp/5.2.177",
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
        "version": 2,
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
            b"Kodi Husimi and Itiro Syozi; 10.1143/ptp/5.2.177; Summary; "
            b"ch 2H = 2; exp(4H) = 3"
            b"</script><p>Visible shell.</p></article></body></html>",
            "title",
        ),
        (200, "text/html", b"<html><body><article>   </article></body></html>", "article"),
        (200, "text/html", OUP_HTML.replace(b"The Statistics of Honeycomb and Triangular Lattice. I", b"Different title"), "title"),
        (200, "text/html", OUP_HTML.replace(b"10.1143/ptp/5.2.177", b"10.1143/wrong"), "DOI"),
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


ROUND7_REDIRECT_SECRET = "Round7/Secret:Token=A9z"


def _round7_credential_profile(secret=ROUND7_REDIRECT_SECRET):
    return {
        "authorization_mode": "request_headers",
        "request_headers_by_origin": {
            "https://api.elsevier.com": {"X-ELS-APIKey": secret},
            "https://redirect.elsevier.com": {
                "Authorization": "Round7RedirectOnlyCredential"
            },
        },
    }


@pytest.mark.parametrize(
    "reflected_secret",
    (
        pytest.param(ROUND7_REDIRECT_SECRET.swapcase(), id="raw-case-variant"),
        pytest.param(
            source_fetcher.quote(ROUND7_REDIRECT_SECRET, safe=""),
            id="percent-encoded",
        ),
        pytest.param(
            source_fetcher.quote(
                source_fetcher.quote(ROUND7_REDIRECT_SECRET, safe=""),
                safe="",
            ),
            id="double-percent-encoded",
        ),
    ),
)
def test_round7_a_redirect_handler_rejects_every_secret_location_before_request(
    reflected_secret,
):
    profile = _round7_credential_profile()
    handler = source_fetcher._CredentialRedirectHandler(profile)
    initial = Request(
        "https://api.elsevier.com/content/article",
        headers={"X-ELS-APIKey": ROUND7_REDIRECT_SECRET},
    )

    with pytest.raises(SourceEvidenceError) as caught:
        handler.redirect_request(
            initial,
            None,
            302,
            "Found",
            {},
            "https://attacker.invalid/capture/" + reflected_secret,
        )

    assert ROUND7_REDIRECT_SECRET.casefold() not in str(caught.value).casefold()


def test_round7_a_two_hop_download_never_issues_secret_bearing_redirect(
    monkeypatch,
):
    profile = _round7_credential_profile()
    encoded = source_fetcher.quote(
        source_fetcher.quote(ROUND7_REDIRECT_SECRET, safe=""),
        safe="",
    )
    issued = []
    payload = _minimal_pdf("Redirect reflection fixture.")

    def opener_factory(*handlers):
        redirect_handler = next(
            handler
            for handler in handlers
            if isinstance(handler, source_fetcher._CredentialRedirectHandler)
        )

        class FixtureOpener:
            def open(self, request, timeout):
                first = redirect_handler.redirect_request(
                    request,
                    None,
                    302,
                    "Found",
                    {},
                    "https://attacker.invalid/capture/" + encoded,
                )
                issued.append(first.full_url)
                second = redirect_handler.redirect_request(
                    first,
                    None,
                    302,
                    "Found",
                    {},
                    "https://clean.example.invalid/final.pdf",
                )
                issued.append(second.full_url)
                return _SignedFixtureResponse(payload, second.full_url)

        return FixtureOpener()

    monkeypatch.setattr(source_fetcher, "build_opener", opener_factory)

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

    assert issued == []
    assert ROUND7_REDIRECT_SECRET.casefold() not in str(caught.value).casefold()


def test_round7_a_redirect_headers_strip_cross_origin_and_reapply_exact_origin():
    profile = _round7_credential_profile()
    handler = source_fetcher._CredentialRedirectHandler(profile)
    initial = Request(
        "https://api.elsevier.com/content/article",
        headers={"X-ELS-APIKey": ROUND7_REDIRECT_SECRET},
    )

    cross_origin = handler.redirect_request(
        initial,
        None,
        302,
        "Found",
        {},
        "https://redirect.elsevier.com.evil.invalid/final",
    )
    exact_origin = handler.redirect_request(
        initial,
        None,
        302,
        "Found",
        {},
        "https://redirect.elsevier.com/final",
    )

    assert not _CREDENTIAL_HEADER_CASEFOLDS.intersection(
        _header_dict(cross_origin)
    )
    assert _header_dict(exact_origin) == {
        "authorization": "Round7RedirectOnlyCredential"
    }


def _round7_author_page_with_head_markup(markup):
    page = AUTHOR_GAREL_PAGE.replace(
        b"<html>",
        b"<html><head>" + markup + b"</head>",
        1,
    )
    assert page != AUTHOR_GAREL_PAGE
    return page


def _round7_oup_page_with_head_markup(markup):
    page = OUP_HTML.replace(b"  </head>", b"    " + markup + b"\n  </head>", 1)
    assert page != OUP_HTML
    return page


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
def test_round7_b_author_complex_hiding_selector_fails_entire_document(extra_doi):
    page = _author_page_with_local_stylesheet(
        b"article .hide-doi { display:none }",
        extra_doi=extra_doi,
    )

    with pytest.raises(SourceEvidenceError, match="style|CSS|validation"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
def test_round7_b_oup_complex_hiding_selector_fails_entire_document(
    tmp_path,
    validation_mode,
    extra_doi,
):
    payload = _oup_payload_with_local_stylesheet(
        b"article .hide-doi { display:none }",
        extra_doi=extra_doi,
    )

    with pytest.raises(SourceEvidenceError, match="style|CSS|validation"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
def test_round7_b_author_inline_css_escape_is_fail_closed_hidden(extra_doi):
    page = _author_page_with_inline_doi_style(
        rb"d\69 splay:none",
        extra_doi=extra_doi,
    )

    if extra_doi:
        _validate_author_garel_page(page)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_author_garel_page(page)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
def test_round7_b_oup_inline_css_escape_is_fail_closed_hidden(
    tmp_path,
    validation_mode,
    extra_doi,
):
    payload = _oup_payload_with_inline_doi_style(
        rb"d\69 splay:none",
        extra_doi=extra_doi,
    )

    if extra_doi:
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)
    else:
        with pytest.raises(SourceEvidenceError, match="DOI"):
            _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize(
    "stylesheet",
    (
        pytest.param(rb".hide-doi { d\69 splay:none }", id="property"),
        pytest.param(rb".hide-doi { display:n\6f ne }", id="value"),
        pytest.param(rb".hide\2d doi { display:none }", id="selector"),
    ),
)
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
def test_round7_b_author_stylesheet_css_escape_fails_entire_document(
    stylesheet,
    extra_doi,
):
    page = _author_page_with_local_stylesheet(stylesheet, extra_doi=extra_doi)

    with pytest.raises(SourceEvidenceError, match="style|CSS|validation"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    "stylesheet",
    (
        pytest.param(rb".hide-doi { d\69 splay:none }", id="property"),
        pytest.param(rb".hide-doi { display:n\6f ne }", id="value"),
        pytest.param(rb".hide\2d doi { display:none }", id="selector"),
    ),
)
@pytest.mark.parametrize("extra_doi", (False, True), ids=("sole", "extra"))
def test_round7_b_oup_stylesheet_css_escape_fails_entire_document(
    tmp_path,
    validation_mode,
    stylesheet,
    extra_doi,
):
    payload = _oup_payload_with_local_stylesheet(
        stylesheet,
        extra_doi=extra_doi,
    )

    with pytest.raises(SourceEvidenceError, match="style|CSS|validation"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("external_css", ("import", "link"))
def test_round7_b_author_external_stylesheet_fails_closed_without_fetch(
    monkeypatch,
    external_css,
):
    monkeypatch.setattr(
        socket,
        "socket",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("CSS validation attempted an external fetch")
        ),
    )
    if external_css == "import":
        page = _author_page_with_local_stylesheet(
            b'@import url("https://styles.example.invalid/author.css");',
            extra_doi=False,
        )
    else:
        page = _round7_author_page_with_head_markup(
            b'<link rel="stylesheet" href="https://styles.example.invalid/author.css">'
        )

    with pytest.raises(SourceEvidenceError, match="style|CSS|validation"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("external_css", ("import", "link"))
def test_round7_b_oup_external_stylesheet_fails_closed_without_fetch(
    tmp_path,
    monkeypatch,
    validation_mode,
    external_css,
):
    monkeypatch.setattr(
        socket,
        "socket",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("CSS validation attempted an external fetch")
        ),
    )
    if external_css == "import":
        payload = _oup_payload_with_local_stylesheet(
            b'@import url("https://styles.example.invalid/oup.css");',
            extra_doi=False,
        )
    else:
        payload = _round7_oup_page_with_head_markup(
            b'<link rel="stylesheet" href="https://styles.example.invalid/oup.css">'
        )

    with pytest.raises(SourceEvidenceError, match="style|CSS|validation"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


def test_round7_b_unknown_nonhiding_complex_rule_remains_ignored():
    page = _author_page_with_local_stylesheet(
        b"article .unused { color:red }",
        extra_doi=False,
    )
    _validate_author_garel_page(page)


def test_round7_b_import_text_still_obeys_stylesheet_character_bound(monkeypatch):
    monkeypatch.setattr(
        evidence_sources,
        "_MAX_LOCAL_STYLESHEET_CHARACTERS",
        24,
    )
    page = _author_page_with_local_stylesheet(
        b'@import url("https://styles.example.invalid/long-name.css");',
        extra_doi=False,
    )

    with pytest.raises(SourceEvidenceError, match="bound|stylesheet"):
        _validate_author_garel_page(page)


def _round7_redirected_author_evidence_fixture():
    route_spec = copy.deepcopy(_author_garel_route())
    request_url = (
        "https://www.lptmc.jussieu.fr/signed/entry"
        "?signature=" + SIGNED_QUERY_SENTINEL + "#request-fragment"
    )
    final_url = (
        "https://www.lptmc.jussieu.fr/redirected/catalog/index.html"
        "?ticket=ROUND7_FINAL_QUERY#final-fragment"
    )
    document_base_url = (
        "https://www.lptmc.jussieu.fr/redirected/catalog/index.html"
    )
    retrieval_url = (
        "https://www.lptmc.jussieu.fr/redirected/catalog/article.pdf"
    )
    route_spec["url"] = retrieval_url
    route_spec["work_identity_evidence"]["url"] = request_url
    page = AUTHOR_GAREL_PAGE.replace(
        b"../../files/maillard/PUB2/Frustrated_jav16i10p2257.pdf",
        b"article.pdf",
        1,
    )
    assert page != AUTHOR_GAREL_PAGE
    return route_spec, page, request_url, final_url, document_base_url


@pytest.mark.parametrize(
    "base_href",
    (
        "https://attacker.example.invalid/capture/",
        "../otherwise-benign/",
    ),
    ids=("attacker", "relative"),
)
def test_round7_c_author_page_rejects_every_base_href(base_href):
    page = _round7_author_page_with_head_markup(
        b'<base href="' + base_href.encode("ascii") + b'">'
    )

    with pytest.raises(SourceEvidenceError, match="base|HTML|validation"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    "base_href",
    (
        "https://attacker.example.invalid/capture/",
        "../otherwise-benign/",
    ),
    ids=("attacker", "relative"),
)
def test_round7_c_oup_rejects_every_base_href(
    tmp_path,
    validation_mode,
    base_href,
):
    payload = _round7_oup_page_with_head_markup(
        b'<base href="' + base_href.encode("ascii") + b'">'
    )

    with pytest.raises(SourceEvidenceError, match="base|HTML|validation"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


def test_round7_c_live_author_relative_link_uses_sanitized_actual_final_base(
    monkeypatch,
):
    (
        route_spec,
        page,
        request_url,
        final_url,
        document_base_url,
    ) = _round7_redirected_author_evidence_fixture()
    captured = []

    class FixtureOpener:
        def open(self, request, timeout):
            captured.append(request.full_url)
            return _FixtureHTTPResponse(
                page,
                content_type="text/html",
                final_url=final_url,
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
                "value": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["doi"],
            }
        },
        {"authoritative_retrieval_route": route_spec},
        object(),
        bibliographic_metadata={
            "title": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["title"],
            "authors": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["authors"],
        },
    )

    assert captured == [request_url]
    assert evidence["descriptor"]["url"] == (
        "https://www.lptmc.jussieu.fr/signed/entry"
    )
    assert evidence["descriptor"]["document_base_url"] == document_base_url
    serialized = json.dumps(evidence["descriptor"], sort_keys=True)
    for secret in (
        SIGNED_QUERY_SENTINEL,
        "request-fragment",
        "ROUND7_FINAL_QUERY",
        "final-fragment",
    ):
        assert secret not in serialized


def test_round7_c_live_author_absolute_link_is_independent_of_final_base(
    monkeypatch,
):
    route_spec = copy.deepcopy(_author_garel_route())
    absolute_page = AUTHOR_GAREL_PAGE.replace(
        b"../../files/maillard/PUB2/Frustrated_jav16i10p2257.pdf",
        route_spec["url"].encode("ascii"),
        1,
    )

    class FixtureOpener:
        def open(self, request, timeout):
            return _FixtureHTTPResponse(
                absolute_page,
                content_type="text/html",
                final_url="https://redirect.example.invalid/unrelated/index.html",
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
                "value": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["doi"],
            }
        },
        {"authoritative_retrieval_route": route_spec},
        object(),
        bibliographic_metadata={
            "title": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["title"],
            "authors": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["authors"],
        },
    )

    assert evidence["payload"] == absolute_page


def test_round7_c_offline_author_relative_link_replays_recorded_document_base(
    tmp_path,
):
    (
        route_spec,
        page,
        _request_url,
        _final_url,
        document_base_url,
    ) = _round7_redirected_author_evidence_fixture()
    source_dir, source, route, _descriptor = _special_sidecar_cache(
        tmp_path,
        "author_publications_same_work",
    )
    route["authoritative_retrieval_route"] = route_spec
    sidecar_path = source_dir / "work-identity.html"
    sidecar_path.write_bytes(page)
    provenance_path = source_dir / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["retrieval_metadata"].update(
        {
            "url": route_spec["url"],
            "immutable_artifact_identifier": route_spec["artifact_identifier"],
            "work_identity_evidence": {
                "kind": "author_publications_same_work",
                "url": "https://www.lptmc.jussieu.fr/signed/entry",
                "document_base_url": document_base_url,
                "media_type": "text/html",
                "payload_relative_path": "work-identity.html",
                "payload_sha256": hashlib.sha256(page).hexdigest(),
                "payload_byte_length": len(page),
            },
        }
    )
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    verified = load_verified_source(
        source_dir,
        expected_source=source,
        provisioning_route=route,
    )

    assert verified.source_id == source["source_id"]


def test_round7_c_work_identity_final_userinfo_is_never_serialized(monkeypatch):
    route_spec = copy.deepcopy(_author_garel_route())

    class FixtureOpener:
        def open(self, request, timeout):
            return _FixtureHTTPResponse(
                AUTHOR_GAREL_PAGE,
                content_type="text/html",
                final_url="https://user:password@www.lptmc.jussieu.fr/private",
            )

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )

    with pytest.raises(SourceEvidenceError, match="userinfo"):
        source_fetcher._fetch_work_identity_evidence(
            {
                "canonical_identity": {
                    "kind": "doi",
                    "value": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["doi"],
                }
            },
            {"authoritative_retrieval_route": route_spec},
            object(),
            bibliographic_metadata={
                "title": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["title"],
                "authors": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["authors"],
            },
        )


def _round7_provenance_fixture():
    source = {
        "source_id": ELSEVIER_SOURCE_ID,
        "canonical_identity": {"kind": "doi", "value": "10.1016/example"},
        "canonical_url": "https://doi.org/10.1016/example",
    }
    route = {
        "authoritative_retrieval_route": {
            "kind": "elsevier_article_api_xml",
            "url": "https://api.elsevier.com/content/article",
            "artifact_identifier": "doi:10.1016/example",
            "work_identity_evidence": {
                "kind": "canonical_identity",
                "url": "https://doi.org/10.1016/example",
            },
        },
        "expected_media_type": "application/pdf",
        "access_mode": "api_key_or_entitlement",
    }
    bibliographic = {
        "title": "Fixture",
        "authors": ["A. Author"],
        "venue": "Fixture",
        "publication_date": "2024-01-01",
    }
    return source, route, bibliographic


def test_round7_d_real_download_to_provenance_uses_explicit_sensitive_values(
    monkeypatch,
):
    source, route, bibliographic = _round7_provenance_fixture()
    payload = _minimal_pdf("Credential-safe production-shape fixture.")
    profile = _round7_credential_profile(MIXED_CASE_CREDENTIAL_SENTINEL)

    class FixtureOpener:
        def open(self, request, timeout):
            response = _SignedFixtureResponse(
                payload,
                "https://api.elsevier.com/content/article",
            )
            response.headers = {
                "Content-Type": "application/pdf",
                "ETag": MIXED_CASE_CREDENTIAL_SENTINEL.swapcase(),
            }
            return response

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )
    monkeypatch.setattr(source_fetcher, "_pdftotext_version", lambda: "fixture")
    response = source_fetcher._download(
        {
            **route["authoritative_retrieval_route"],
            "expected_media_type": "application/pdf",
        },
        object(),
        credential_profile=profile,
    )

    assert "credential_values" not in response
    provenance = source_fetcher._build_provenance(
        source,
        route,
        response,
        bibliographic,
        payload_name="source.pdf",
        sensitive_values=(MIXED_CASE_CREDENTIAL_SENTINEL,),
    )

    assert MIXED_CASE_CREDENTIAL_SENTINEL.casefold() not in json.dumps(
        provenance,
        sort_keys=True,
    ).casefold()


@pytest.mark.parametrize(
    "collision",
    (
        pytest.param(
            {"nested": [{"value": MIXED_CASE_CREDENTIAL_SENTINEL.swapcase()}]},
            id="nested-value",
        ),
        pytest.param(
            {MIXED_CASE_CREDENTIAL_SENTINEL.swapcase(): {"value": "safe"}},
            id="nested-key",
        ),
    ),
)
def test_round7_d_recursive_provenance_collision_fails_closed_without_secret(
    monkeypatch,
    collision,
):
    source, route, bibliographic = _round7_provenance_fixture()
    monkeypatch.setattr(source_fetcher, "_pdftotext_version", lambda: "fixture")
    response = {
        "body": _minimal_pdf("Credential-safe provenance fixture."),
        "final_url": "https://api.elsevier.com/content/article",
        "status": 200,
        "headers": {"Content-Type": "application/pdf"},
        "media_type": "application/pdf",
    }
    bibliographic = {**bibliographic, "recursive_extension": collision}

    with pytest.raises(SourceEvidenceError) as caught:
        source_fetcher._build_provenance(
            source,
            route,
            response,
            bibliographic,
            payload_name="source.pdf",
            sensitive_values=(MIXED_CASE_CREDENTIAL_SENTINEL,),
        )

    assert MIXED_CASE_CREDENTIAL_SENTINEL.casefold() not in str(caught.value).casefold()


def test_round7_d_fetch_source_passes_secrets_and_fails_before_any_cache_write(
    tmp_path,
    monkeypatch,
):
    source, route, bibliographic = _round7_provenance_fixture()
    cache_root = tmp_path / "cache"
    source_dir = cache_root / source["source_id"]
    profile = _round7_credential_profile(MIXED_CASE_CREDENTIAL_SENTINEL)
    bibliographic = {
        **bibliographic,
        "recursive_extension": {
            "records": [MIXED_CASE_CREDENTIAL_SENTINEL.swapcase()]
        },
    }
    response = {
        "body": _minimal_pdf("Credential-safe fetch-source fixture."),
        "final_url": "https://api.elsevier.com/content/article",
        "status": 200,
        "headers": {"Content-Type": "application/pdf"},
        "media_type": "application/pdf",
    }
    monkeypatch.setattr(source_fetcher, "_ssl_context", lambda ca_bundle: object())
    monkeypatch.setattr(source_fetcher, "_download", lambda *args, **kwargs: response)
    monkeypatch.setattr(
        source_fetcher,
        "_fetch_bibliographic_metadata",
        lambda *args, **kwargs: bibliographic,
    )
    monkeypatch.setattr(
        source_fetcher,
        "_fetch_work_identity_evidence",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(source_fetcher, "_pdftotext_version", lambda: "fixture")

    outcome = source_fetcher._fetch_source(
        cache_root,
        source,
        route,
        ca_bundle=Path("/unused"),
        resume=False,
        credential_profile=profile,
    )

    assert outcome["status"] == "failed"
    assert not source_dir.exists()
    assert MIXED_CASE_CREDENTIAL_SENTINEL.casefold() not in (
        " ".join(_recursive_strings(outcome)).casefold()
    )


def _round7_resume_route():
    route = copy.deepcopy(_provisioning())
    route["authoritative_retrieval_route"].update(
        {
            "artifact_identifier": f"doi:{DOI}",
            "work_identity_evidence": {
                "kind": "canonical_identity",
                "url": CANONICAL_URL,
            },
        }
    )
    return route


def _round7_tree_snapshot(path):
    path = Path(path)
    stat_result = path.lstat()
    common = (
        stat_result.st_mode,
        stat_result.st_size,
        stat_result.st_mtime_ns,
    )
    if path.is_symlink():
        return ("symlink", common, os.readlink(path))
    if path.is_file():
        return ("file", common, path.read_bytes())
    return (
        "directory",
        common,
        tuple(
            (child.name, _round7_tree_snapshot(child))
            for child in sorted(path.iterdir(), key=lambda item: item.name)
        ),
    )


def _round7_forbid_resume_supplement(monkeypatch):
    events = []

    def forbidden(name):
        def fail(*args, **kwargs):
            events.append(name)
            raise AssertionError(f"resume attempted forbidden operation: {name}")

        return fail

    for name in (
        "_ssl_context",
        "_download",
        "_fetch_bibliographic_metadata",
        "_fetch_work_identity_evidence",
        "_write_work_identity_sidecars",
    ):
        monkeypatch.setattr(source_fetcher, name, forbidden(name))
    return events


def _round7_invalid_resume_cache(tmp_path, mutation):
    source_dir = tmp_path / SOURCE_ID
    source_dir.mkdir(parents=True)
    payload = PAYLOAD
    provenance = _provenance(payload)
    if mutation == "payload":
        payload += b"\ncorrupted"
    elif mutation == "hash":
        provenance["raw_payload_sha256"] = "0" * 64
    elif mutation == "identity":
        provenance["source_identity"]["value"] = "10.1234/different"
    elif mutation == "path":
        provenance["payload_relative_path"] = "../source.xml"
    elif mutation == "provenance":
        source_dir.joinpath("source.xml").write_bytes(payload)
        source_dir.joinpath("provenance.json").write_bytes(b"{not-json")
        return source_dir
    elif mutation == "payload-symlink":
        target = tmp_path / "user-owned-payload.xml"
        target.write_bytes(payload)
        source_dir.joinpath("source.xml").symlink_to(target)
        source_dir.joinpath("provenance.json").write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return source_dir
    else:
        raise AssertionError(f"unknown resume mutation {mutation}")
    source_dir.joinpath("source.xml").write_bytes(payload)
    source_dir.joinpath("provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return source_dir


def test_round7_e_resume_verified_cache_skips_all_network_and_writes(
    tmp_path,
    monkeypatch,
):
    source_dir = _write_source(tmp_path)
    before = _round7_tree_snapshot(source_dir)
    events = _round7_forbid_resume_supplement(monkeypatch)

    outcome = source_fetcher._fetch_source(
        tmp_path,
        _expected_source(),
        _round7_resume_route(),
        ca_bundle=Path("/unused"),
        resume=True,
    )

    assert outcome == {
        "source_id": SOURCE_ID,
        "status": "resumed",
        "detail": "existing cache verified",
    }
    assert events == []
    assert _round7_tree_snapshot(source_dir) == before


@pytest.mark.parametrize(
    "mutation",
    ("payload", "hash", "identity", "provenance", "path", "payload-symlink"),
)
def test_round7_e_invalid_resume_cache_is_failed_and_byte_for_byte_unchanged(
    tmp_path,
    monkeypatch,
    mutation,
):
    source_dir = _round7_invalid_resume_cache(tmp_path, mutation)
    before = _round7_tree_snapshot(tmp_path)
    events = _round7_forbid_resume_supplement(monkeypatch)

    outcome = source_fetcher._fetch_source(
        tmp_path,
        _expected_source(),
        _round7_resume_route(),
        ca_bundle=Path("/unused"),
        resume=True,
    )

    assert outcome["status"] == "failed"
    assert events == []
    assert _round7_tree_snapshot(tmp_path) == before
    assert source_dir.exists()


def test_round7_e_resume_rejects_symlink_source_directory_without_following_it(
    tmp_path,
    monkeypatch,
):
    target_root = tmp_path / "user-owned-cache"
    target_dir = _write_source(target_root)
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    source_link = cache_root / SOURCE_ID
    source_link.symlink_to(target_dir, target_is_directory=True)
    link_before = _round7_tree_snapshot(source_link)
    target_before = _round7_tree_snapshot(target_dir)
    events = _round7_forbid_resume_supplement(monkeypatch)

    outcome = source_fetcher._fetch_source(
        cache_root,
        _expected_source(),
        _round7_resume_route(),
        ca_bundle=Path("/unused"),
        resume=True,
    )

    assert outcome["status"] == "failed"
    assert "symlink" in outcome["detail"].casefold()
    assert events == []
    assert _round7_tree_snapshot(source_link) == link_before
    assert _round7_tree_snapshot(target_dir) == target_before


def test_round7_e_missing_sidecar_never_triggers_resume_supplement_or_write(
    tmp_path,
    monkeypatch,
):
    source_dir, source, route, descriptor = _special_sidecar_cache(
        tmp_path,
        "author_publications_same_work",
        write_sidecar=False,
    )
    assert not source_dir.joinpath(descriptor["payload_relative_path"]).exists()
    before = _round7_tree_snapshot(source_dir)
    events = _round7_forbid_resume_supplement(monkeypatch)

    outcome = source_fetcher._fetch_source(
        tmp_path,
        source,
        route,
        ca_bundle=Path("/unused"),
        resume=True,
    )

    assert outcome["status"] == "failed"
    assert events == []
    assert _round7_tree_snapshot(source_dir) == before
    assert not source_dir.joinpath(descriptor["payload_relative_path"]).exists()


def test_round7_e_any_unexpected_loader_failure_is_failed_without_mutation(
    tmp_path,
    monkeypatch,
):
    source_dir = _write_source(tmp_path)
    before = _round7_tree_snapshot(source_dir)
    events = _round7_forbid_resume_supplement(monkeypatch)
    monkeypatch.setattr(
        source_fetcher,
        "load_verified_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("opaque loader failure")
        ),
    )

    outcome = source_fetcher._fetch_source(
        tmp_path,
        _expected_source(),
        _round7_resume_route(),
        ca_bundle=Path("/unused"),
        resume=True,
    )

    assert outcome["status"] == "failed"
    assert "opaque loader failure" in outcome["detail"]
    assert events == []
    assert _round7_tree_snapshot(source_dir) == before


def _round7_signed_sidecar_roundtrip_fixture(evidence_kind):
    if evidence_kind == "author_publications_same_work":
        route_spec, page, _request, _final, _base = (
            _round7_redirected_author_evidence_fixture()
        )
        identity_value = AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["doi"]
        bibliographic = {
            "title": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["title"],
            "authors": AUTHOR_GAREL_BIBLIOGRAPHIC_METADATA["authors"],
            "venue": "Journal of Physics A",
            "publication_date": "1983-01-01",
        }
        signed_query = "ROUND7_AUTHOR_SIGNED_QUERY"
        request_fragment = "round7-author-request-fragment"
        final_query = "ROUND7_AUTHOR_FINAL_QUERY"
        final_fragment = "round7-author-final-fragment"
        route_spec["work_identity_evidence"]["url"] = (
            "https://www.lptmc.jussieu.fr/signed/author-entry"
            f"?signature={signed_query}#{request_fragment}"
        )
        sidecar_payload = page
        sidecar_media_type = "text/html"
        sidecar_final_url = (
            "https://www.lptmc.jussieu.fr/redirected/catalog/index.html"
            f"?ticket={final_query}#{final_fragment}"
        )
        document_base_url = (
            "https://www.lptmc.jussieu.fr/redirected/catalog/index.html"
        )
    elif evidence_kind == "core_same_work_output":
        route_spec = copy.deepcopy(_core_mg_route())
        identity_value = CORE_MG_BIBLIOGRAPHIC_METADATA["doi"]
        bibliographic = {
            "title": CORE_MG_BIBLIOGRAPHIC_METADATA["title"],
            "authors": CORE_MG_BIBLIOGRAPHIC_METADATA["authors"],
            "venue": "Journal of Physics A",
            "publication_date": "1984-01-01",
        }
        signed_query = "ROUND7_CORE_SIGNED_QUERY"
        request_fragment = "round7-core-request-fragment"
        final_query = "ROUND7_CORE_FINAL_QUERY"
        final_fragment = "round7-core-final-fragment"
        route_spec["work_identity_evidence"]["url"] = (
            "https://api.core.ac.uk/v3/outputs/572184419"
            f"?signature={signed_query}#{request_fragment}"
        )
        sidecar_payload = json.dumps(
            _core_mg_work_identity_document(),
            sort_keys=True,
        ).encode("utf-8")
        sidecar_media_type = "application/json"
        sidecar_final_url = (
            "https://api.core.ac.uk/resolved/outputs/572184419"
            f"?ticket={final_query}#{final_fragment}"
        )
        document_base_url = (
            "https://api.core.ac.uk/resolved/outputs/572184419"
        )
    else:
        raise AssertionError(f"unknown evidence kind {evidence_kind}")

    source_id = "doi_" + hashlib.sha256(
        f"doi:{identity_value}".encode("ascii")
    ).hexdigest()[:20]
    source = {
        "source_id": source_id,
        "canonical_identity": {"kind": "doi", "value": identity_value},
        "canonical_url": f"https://doi.org/{identity_value}",
        "benchmark_names": ["round7_signed_sidecar_fixture"],
    }
    route = {
        "source_id": source_id,
        "authoritative_retrieval_route": route_spec,
        "expected_media_type": "application/pdf",
        "access_mode": "unattended",
        "local_cache_location": f"source-cache/{source_id}/source.pdf",
    }
    return {
        "source": source,
        "route": route,
        "bibliographic": bibliographic,
        "primary_payload": _minimal_pdf(
            f"Round seven {evidence_kind} signed-sidecar roundtrip."
        ),
        "sidecar_payload": sidecar_payload,
        "sidecar_media_type": sidecar_media_type,
        "sidecar_final_url": sidecar_final_url,
        "document_base_url": document_base_url,
        "signed_query": signed_query,
        "request_fragment": request_fragment,
        "final_query": final_query,
        "final_fragment": final_fragment,
    }


@pytest.mark.parametrize(
    "evidence_kind",
    ("author_publications_same_work", "core_same_work_output"),
)
def test_round7_f_signed_sidecar_full_fetch_write_and_offline_roundtrip(
    tmp_path,
    monkeypatch,
    evidence_kind,
):
    fixture = _round7_signed_sidecar_roundtrip_fixture(evidence_kind)
    source = fixture["source"]
    route = fixture["route"]
    route_spec = route["authoritative_retrieval_route"]
    sidecar_request_url = route_spec["work_identity_evidence"]["url"]
    primary_final_url = route_spec["url"] + (
        "?download=ROUND7_PRIMARY_FINAL_QUERY#round7-primary-final-fragment"
    )
    requests = []

    class FixtureOpener:
        def open(self, request, timeout):
            requests.append(request.full_url)
            accept = _header_dict(request).get("accept")
            if accept == "application/pdf":
                return _FixtureHTTPResponse(
                    fixture["primary_payload"],
                    content_type="application/pdf",
                    final_url=primary_final_url,
                )
            assert accept == fixture["sidecar_media_type"]
            return _FixtureHTTPResponse(
                fixture["sidecar_payload"],
                content_type=fixture["sidecar_media_type"],
                final_url=fixture["sidecar_final_url"],
            )

    monkeypatch.setattr(source_fetcher, "_ssl_context", lambda ca_bundle: object())
    monkeypatch.setattr(
        source_fetcher,
        "_fetch_bibliographic_metadata",
        lambda *args, **kwargs: dict(fixture["bibliographic"]),
    )
    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )

    outcome = source_fetcher._fetch_source(
        tmp_path,
        source,
        route,
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert outcome["status"] == "acquired"
    source_dir = tmp_path / source["source_id"]
    verified = load_verified_source(
        source_dir,
        expected_source=source,
        provisioning_route=route,
    )
    assert verified.source_id == source["source_id"]
    assert sidecar_request_url in requests
    descriptor = json.loads(
        source_dir.joinpath("work-identity.provenance.json").read_text(
            encoding="utf-8"
        )
    )
    expected_stable_route = sidecar_request_url.split("?", 1)[0]
    assert descriptor["url"] == expected_stable_route
    assert descriptor["document_base_url"] == fixture["document_base_url"]
    assert descriptor["url"] != descriptor["document_base_url"]
    serialized_cache = b"\n".join(
        path.read_bytes() for path in sorted(source_dir.iterdir()) if path.is_file()
    )
    for forbidden in (
        fixture["signed_query"],
        fixture["request_fragment"],
        fixture["final_query"],
        fixture["final_fragment"],
        "ROUND7_PRIMARY_FINAL_QUERY",
        "round7-primary-final-fragment",
        ROUND7_REDIRECT_SECRET,
    ):
        assert forbidden.encode("utf-8") not in serialized_cache


@pytest.mark.parametrize(
    ("kind", "stable_url", "signed_url"),
    (
        (
            "author_publications_same_work",
            "https://www.lptmc.jussieu.fr/signed/author-entry",
            "https://www.lptmc.jussieu.fr/signed/author-entry?signature=secret#fragment",
        ),
        (
            "core_same_work_output",
            "https://api.core.ac.uk/v3/outputs/572184419",
            "https://api.core.ac.uk/v3/outputs/572184419?signature=secret#fragment",
        ),
    ),
)
def test_round7_f_route_match_compares_same_sanitized_stable_identity(
    kind,
    stable_url,
    signed_url,
):
    assert evidence_sources._same_work_identity_route(
        {"kind": kind, "url": stable_url},
        {"kind": kind, "url": signed_url},
    )


@pytest.mark.parametrize(
    "stored",
    (
        {
            "kind": "author_publications_same_work",
            "url": "https://www.lptmc.jussieu.fr/signed/author-entry/extra",
        },
        {
            "kind": "author_publications_same_work",
            "url": "https://www.lptmc.jussieu.fr.evil.invalid/signed/author-entry",
        },
        {
            "kind": "core_same_work_output",
            "url": "https://www.lptmc.jussieu.fr/signed/author-entry",
        },
    ),
    ids=("path-suffix", "lookalike-host", "kind-mismatch"),
)
def test_round7_f_route_match_rejects_every_nonexact_identity(stored):
    expected = {
        "kind": "author_publications_same_work",
        "url": (
            "https://www.lptmc.jussieu.fr/signed/author-entry"
            "?signature=secret#fragment"
        ),
    }
    assert not evidence_sources._same_work_identity_route(stored, expected)


@pytest.mark.parametrize(
    "unsafe_url",
    (
        "https://api.core.ac.uk/v3/outputs/572184419?signature=secret",
        "https://api.core.ac.uk/v3/outputs/572184419#fragment",
        "https://user:password@api.core.ac.uk/v3/outputs/572184419",
    ),
    ids=("query", "fragment", "userinfo"),
)
def test_round7_f_serialized_route_identity_rejects_all_secret_bearing_forms(
    unsafe_url,
):
    with pytest.raises(SourceEvidenceError, match="query|fragment|userinfo"):
        evidence_sources._validate_serialized_https_url(
            unsafe_url,
            "round7 stable route identity",
        )


ROUND8_CLOSED_BASE_TAGS = (
    pytest.param(b"<base>", id="no-attributes"),
    pytest.param(b'<base id="round8-base">', id="no-href"),
    pytest.param(b'<base target="_blank">', id="target-only"),
    pytest.param(b"<base/>", id="self-closing"),
    pytest.param(b"<BASE>", id="uppercase"),
)


@pytest.mark.parametrize("base_tag", ROUND8_CLOSED_BASE_TAGS)
def test_round8_c_author_rejects_every_base_tag_in_closed_html_subset(base_tag):
    page = _round7_author_page_with_head_markup(base_tag)

    with pytest.raises(SourceEvidenceError, match="base|HTML|validation"):
        _validate_author_garel_page(page)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize("base_tag", ROUND8_CLOSED_BASE_TAGS)
def test_round8_c_oup_rejects_every_base_tag_in_closed_html_subset(
    tmp_path,
    validation_mode,
    base_tag,
):
    payload = _round7_oup_page_with_head_markup(base_tag)

    with pytest.raises(SourceEvidenceError, match="base|HTML|validation"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


ROUND8_HEADER_NAME_SECRET = "Round8!HeaderTokenA9z"
ROUND8_HEADER_SECRET_VARIANTS = (
    pytest.param(ROUND8_HEADER_NAME_SECRET, id="raw"),
    pytest.param(ROUND8_HEADER_NAME_SECRET.casefold(), id="casefold"),
    pytest.param(
        source_fetcher.quote(ROUND8_HEADER_NAME_SECRET, safe=""),
        id="percent-encoded",
    ),
    pytest.param(
        source_fetcher.quote(
            source_fetcher.quote(ROUND8_HEADER_NAME_SECRET, safe=""),
            safe="",
        ),
        id="double-percent-encoded",
    ),
)


def _round8_header_credential_profile():
    return {
        "authorization_mode": "request_headers",
        "request_headers_by_origin": {
            "https://api.elsevier.com": {
                "X-ELS-APIKey": ROUND8_HEADER_NAME_SECRET
            }
        },
    }


def _round8_download_route():
    return {
        "kind": "elsevier_article_api_xml",
        "url": "https://api.elsevier.com/content/article",
        "expected_media_type": "application/pdf",
    }


def _round8_install_download_response(monkeypatch, headers):
    payload = _minimal_pdf("Round eight response-boundary fixture.")

    class FixtureOpener:
        def open(self, request, timeout):
            response = _SignedFixtureResponse(
                payload,
                "https://api.elsevier.com/content/article",
            )
            response.headers = headers
            return response

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )
    return payload


@pytest.mark.parametrize("reflected_name", ROUND8_HEADER_SECRET_VARIANTS)
def test_round8_d_download_fails_closed_on_secret_response_header_name(
    monkeypatch,
    reflected_name,
):
    _round8_install_download_response(
        monkeypatch,
        {
            "Content-Type": "application/pdf",
            "X-Reflected-" + reflected_name: "safe-value",
        },
    )
    returned = []

    with pytest.raises(SourceEvidenceError) as caught:
        returned.append(
            source_fetcher._download(
                _round8_download_route(),
                object(),
                credential_profile=_round8_header_credential_profile(),
            )
        )

    assert returned == []
    rendered = str(caught.value).casefold()
    assert ROUND8_HEADER_NAME_SECRET.casefold() not in rendered
    assert reflected_name.casefold() not in rendered


@pytest.mark.parametrize("reflected_value", ROUND8_HEADER_SECRET_VARIANTS)
def test_round8_d_download_omits_encoded_secret_header_values_from_mapping(
    monkeypatch,
    reflected_value,
):
    _round8_install_download_response(
        monkeypatch,
        {
            "Content-Type": "application/pdf",
            "ETag": "reflected-" + reflected_value,
        },
    )

    response = source_fetcher._download(
        _round8_download_route(),
        object(),
        credential_profile=_round8_header_credential_profile(),
    )

    assert "ETag" not in response["headers"]
    assert not source_fetcher._contains_sensitive(
        response,
        (ROUND8_HEADER_NAME_SECRET,),
    )


def test_round8_d_download_response_mapping_has_recursive_secret_postcondition(
    monkeypatch,
):
    _round8_install_download_response(
        monkeypatch,
        {"Content-Type": "application/pdf"},
    )
    reflected_media_type = "application/" + source_fetcher.quote(
        source_fetcher.quote(ROUND8_HEADER_NAME_SECRET, safe=""),
        safe="",
    )
    monkeypatch.setattr(
        source_fetcher,
        "validate_download_response",
        lambda *args, **kwargs: reflected_media_type,
    )

    with pytest.raises(SourceEvidenceError) as caught:
        source_fetcher._download(
            _round8_download_route(),
            object(),
            credential_profile=_round8_header_credential_profile(),
        )

    assert ROUND8_HEADER_NAME_SECRET.casefold() not in str(caught.value).casefold()


def test_round8_d_secret_header_name_stops_fetch_before_artifact_generation(
    tmp_path,
    monkeypatch,
):
    source, route, bibliographic = _round7_provenance_fixture()
    cache_root = tmp_path / "cache"
    source_dir = cache_root / source["source_id"]
    events = []
    _round8_install_download_response(
        monkeypatch,
        {
            "Content-Type": "application/pdf",
            "X-Reflected-" + ROUND8_HEADER_NAME_SECRET.swapcase(): "safe-value",
        },
    )
    monkeypatch.setattr(source_fetcher, "_ssl_context", lambda ca_bundle: object())

    def tracked_bibliographic(*args, **kwargs):
        events.append("bibliographic")
        return bibliographic

    monkeypatch.setattr(
        source_fetcher,
        "_fetch_bibliographic_metadata",
        tracked_bibliographic,
    )

    outcome = source_fetcher._fetch_source(
        cache_root,
        source,
        route,
        ca_bundle=Path("/unused"),
        resume=False,
        credential_profile=_round8_header_credential_profile(),
    )

    assert outcome["status"] == "failed"
    assert events == []
    assert not source_dir.exists()
    assert not source_fetcher._contains_sensitive(
        outcome,
        (ROUND8_HEADER_NAME_SECRET,),
    )


def test_round8_d_normal_response_headers_remain_available_control(monkeypatch):
    _round8_install_download_response(
        monkeypatch,
        {
            "Content-Type": "application/pdf",
            "ETag": "round8-safe-etag",
            "Last-Modified": "Sat, 01 Aug 2026 00:00:00 GMT",
        },
    )

    response = source_fetcher._download(
        _round8_download_route(),
        object(),
        credential_profile=_round8_header_credential_profile(),
    )

    assert response["headers"] == {
        "Content-Type": "application/pdf",
        "ETag": "round8-safe-etag",
        "Last-Modified": "Sat, 01 Aug 2026 00:00:00 GMT",
    }
    assert not source_fetcher._contains_sensitive(
        response,
        (ROUND8_HEADER_NAME_SECRET,),
    )


ROUND9_SPACED_SECRET = "Authorization: Bearer TOKEN 42"
ROUND9_QUERY_LIMIT = 16 * 1024


def _round9_credential_profile():
    return {
        "authorization_mode": "request_headers",
        "request_headers_by_origin": {
            "https://api.elsevier.com": {
                "Authorization": ROUND9_SPACED_SECRET,
            },
        },
    }


def _round9_redirect_handler():
    return source_fetcher._CredentialRedirectHandler(
        _round9_credential_profile()
    )


def _round9_initial_request():
    return Request(
        "https://api.elsevier.com/content/article",
        headers={"Authorization": ROUND9_SPACED_SECRET},
    )


def test_round9_cross_origin_quote_plus_secret_rejected_before_request_construction(
    monkeypatch,
):
    super_calls = []

    def forbidden_super(*args, **kwargs):
        super_calls.append((args, kwargs))
        raise AssertionError("redirect Request construction was reached")

    monkeypatch.setattr(
        source_fetcher.HTTPRedirectHandler,
        "redirect_request",
        forbidden_super,
    )
    reflected = quote_plus(ROUND9_SPACED_SECRET, safe="")

    with pytest.raises(SourceEvidenceError) as caught:
        _round9_redirect_handler().redirect_request(
            _round9_initial_request(),
            None,
            302,
            "Found",
            {},
            "https://attacker.invalid/capture?ref=" + reflected,
        )

    assert super_calls == []
    assert ROUND9_SPACED_SECRET.casefold() not in str(caught.value).casefold()


def test_round9_two_redirects_stop_before_form_secret_second_request(monkeypatch):
    issued_redirects = []
    unsafe_intermediate = (
        "https://attacker.invalid/intermediate?ref="
        + quote_plus(ROUND9_SPACED_SECRET, safe="")
    )

    def opener_factory(*handlers):
        redirect_handler = next(
            handler
            for handler in handlers
            if isinstance(handler, source_fetcher._CredentialRedirectHandler)
        )

        class FixtureOpener:
            def open(self, request, timeout):
                first = redirect_handler.redirect_request(
                    request,
                    None,
                    302,
                    "Found",
                    {},
                    "https://redirect.example.invalid/safe-intermediate",
                )
                issued_redirects.append(first.full_url)
                second = redirect_handler.redirect_request(
                    first,
                    None,
                    302,
                    "Found",
                    {},
                    unsafe_intermediate,
                )
                issued_redirects.append(second.full_url)
                raise AssertionError("unsafe second redirect was issued")

        return FixtureOpener()

    monkeypatch.setattr(source_fetcher, "build_opener", opener_factory)

    with pytest.raises(SourceEvidenceError) as caught:
        source_fetcher._download(
            {
                "kind": "elsevier_article_api_xml",
                "url": "https://api.elsevier.com/content/article",
                "expected_media_type": "application/pdf",
            },
            object(),
            credential_profile=_round9_credential_profile(),
        )

    assert issued_redirects == [
        "https://redirect.example.invalid/safe-intermediate"
    ]
    assert ROUND9_SPACED_SECRET.casefold() not in str(caught.value).casefold()


def test_round9_same_origin_quote_plus_secret_is_rejected():
    reflected = quote_plus(ROUND9_SPACED_SECRET, safe="")

    with pytest.raises(SourceEvidenceError) as caught:
        _round9_redirect_handler().redirect_request(
            _round9_initial_request(),
            None,
            302,
            "Found",
            {},
            "https://api.elsevier.com/content/article?ref=" + reflected,
        )

    assert ROUND9_SPACED_SECRET.casefold() not in str(caught.value).casefold()


@pytest.mark.parametrize(
    "reflected",
    (
        pytest.param(
            quote_plus(ROUND9_SPACED_SECRET, safe=""),
            id="literal-plus",
        ),
        pytest.param(
            quote_plus(ROUND9_SPACED_SECRET, safe="").replace("+", "%2B"),
            id="percent-plus",
        ),
        pytest.param(
            quote_plus(ROUND9_SPACED_SECRET, safe="").replace("+", "%252B"),
            id="double-percent-plus",
        ),
        pytest.param(
            quote_plus(ROUND9_SPACED_SECRET, safe="").replace(
                "+", "%25252B"
            ),
            id="deep-percent-plus",
        ),
        pytest.param(
            quote_plus(ROUND9_SPACED_SECRET, safe="")
            .replace("+", "%2B", 1)
            .replace("+", "%252B", 1),
            id="mixed-plus-percent-double-percent",
        ),
    ),
)
def test_round9_query_form_and_mixed_bounded_variants_are_rejected(reflected):
    with pytest.raises(SourceEvidenceError) as caught:
        _round9_redirect_handler().redirect_request(
            _round9_initial_request(),
            None,
            302,
            "Found",
            {},
            "https://attacker.invalid/capture?ref=" + reflected,
        )

    assert ROUND9_SPACED_SECRET.casefold() not in str(caught.value).casefold()


@pytest.mark.parametrize(
    "reflected",
    (
        pytest.param(ROUND9_SPACED_SECRET, id="raw"),
        pytest.param(ROUND9_SPACED_SECRET.swapcase(), id="case-variant"),
        pytest.param(
            source_fetcher.quote(ROUND9_SPACED_SECRET, safe=""),
            id="percent-space",
        ),
        pytest.param(
            source_fetcher.quote(
                source_fetcher.quote(ROUND9_SPACED_SECRET, safe=""),
                safe="",
            ),
            id="double-percent-space",
        ),
    ),
)
def test_round9_existing_raw_case_and_percent_secret_checks_remain(reflected):
    with pytest.raises(SourceEvidenceError) as caught:
        _round9_redirect_handler().redirect_request(
            _round9_initial_request(),
            None,
            302,
            "Found",
            {},
            "https://attacker.invalid/capture?ref=" + reflected,
        )

    assert ROUND9_SPACED_SECRET.casefold() not in str(caught.value).casefold()


def test_round9_distinct_signed_query_with_common_encodings_is_allowed():
    signed_url = (
        "https://attacker.invalid/download"
        "?signature=distinct+signed%2Btoken%20value%252541"
        "&ticket=unrelated%20credential"
    )

    redirected = _round9_redirect_handler().redirect_request(
        _round9_initial_request(),
        None,
        302,
        "Found",
        {},
        signed_url,
    )

    assert redirected.full_url == signed_url
    assert not _CREDENTIAL_HEADER_CASEFOLDS.intersection(
        _header_dict(redirected)
    )


@pytest.mark.parametrize(
    "path",
    (
        pytest.param(
            "/capture/Authorization:+Bearer+TOKEN+42",
            id="secret-space-form-is-not-path-space",
        ),
        pytest.param(
            "/files/distinct+signed+path",
            id="unrelated-literal-plus",
        ),
    ),
)
def test_round9_literal_plus_in_path_is_not_given_form_query_semantics(path):
    redirected = _round9_redirect_handler().redirect_request(
        _round9_initial_request(),
        None,
        302,
        "Found",
        {},
        "https://attacker.invalid" + path + "?signature=distinct%20value",
    )

    assert redirected.full_url.startswith("https://attacker.invalid" + path)
    assert not _CREDENTIAL_HEADER_CASEFOLDS.intersection(
        _header_dict(redirected)
    )


def test_round9_query_over_sixteen_kib_fails_closed_before_request(monkeypatch):
    super_calls = []

    def forbidden_super(*args, **kwargs):
        super_calls.append((args, kwargs))
        raise AssertionError("redirect Request construction was reached")

    monkeypatch.setattr(
        source_fetcher.HTTPRedirectHandler,
        "redirect_request",
        forbidden_super,
    )
    oversized_query = "signature=" + "x" * ROUND9_QUERY_LIMIT

    with pytest.raises(SourceEvidenceError) as caught:
        _round9_redirect_handler().redirect_request(
            _round9_initial_request(),
            None,
            302,
            "Found",
            {},
            "https://attacker.invalid/download?" + oversized_query,
        )

    assert super_calls == []
    assert ROUND9_SPACED_SECRET.casefold() not in str(caught.value).casefold()


def test_round9_query_at_sixteen_kib_with_distinct_signature_is_allowed():
    query = "signature=" + "x" * (ROUND9_QUERY_LIMIT - len("signature="))
    signed_url = "https://attacker.invalid/download?" + query

    redirected = _round9_redirect_handler().redirect_request(
        _round9_initial_request(),
        None,
        302,
        "Found",
        {},
        signed_url,
    )

    assert redirected.full_url == signed_url


def _round10_credential_profile(secret):
    return {
        "authorization_mode": "request_headers",
        "request_headers_by_origin": {
            "https://api.elsevier.com": {"Authorization": secret},
        },
    }


def _round10_redirect_handler(secret=ROUND9_SPACED_SECRET):
    return source_fetcher._CredentialRedirectHandler(
        _round10_credential_profile(secret)
    )


def _round10_initial_request(secret=ROUND9_SPACED_SECRET):
    return Request(
        "https://api.elsevier.com/content/article",
        headers={"Authorization": secret},
    )


def _round10_expand_every_character(value, depth, *, lowercase_first=False):
    current = value
    for layer in range(depth):
        format_code = "02x" if lowercase_first and layer == 0 else "02X"
        current = "".join(
            f"%{format(ord(character), format_code)}" for character in current
        )
    return current


def _round10_reviewer_reflection(secret=ROUND9_SPACED_SECRET, *, depth=4):
    encoded_space = _round10_expand_every_character("+", depth)
    return secret.replace(" ", encoded_space)


def _round10_reference_form_stages(value, *, maximum_passes=16):
    stages = [value]
    for _ in range(maximum_passes):
        decoded = unquote_plus(stages[-1], errors="replace")
        if decoded == stages[-1]:
            return tuple(stages)
        stages.append(decoded)
    raise AssertionError("test fixture exceeds the finite reference depth")


def _round10_reference_contains_secret(query, secret):
    folded_secret = secret.casefold()
    return any(
        folded_secret in stage.casefold()
        for stage in _round10_reference_form_stages(query)
    )


def _round10_assert_generic_rejection(caught, *, forbidden_values):
    rendered = str(caught.value).casefold()
    assert rendered == "request url contains sensitive data"
    for value in forbidden_values:
        assert value.casefold() not in rendered


def test_round10_depth_four_expanded_cross_origin_secret_stops_before_super(
    monkeypatch,
):
    super_calls = []

    def forbidden_super(*args, **kwargs):
        super_calls.append((args, kwargs))
        raise AssertionError("redirect Request construction was reached")

    monkeypatch.setattr(
        source_fetcher.HTTPRedirectHandler,
        "redirect_request",
        forbidden_super,
    )
    reflected = _round10_reviewer_reflection()
    query = "ref=" + reflected
    target = "https://attacker.invalid/capture?" + query
    stages = _round10_reference_form_stages(query)

    assert len(query) == 274
    assert ROUND9_SPACED_SECRET not in stages[:-1]
    assert ROUND9_SPACED_SECRET in stages[-1]

    with pytest.raises(SourceEvidenceError) as caught:
        _round10_redirect_handler().redirect_request(
            _round10_initial_request(),
            None,
            302,
            "Found",
            {},
            target,
        )

    assert super_calls == []
    _round10_assert_generic_rejection(
        caught,
        forbidden_values=(ROUND9_SPACED_SECRET, reflected, query, target, *stages),
    )


def test_round10_depth_four_expanded_secret_stops_unsafe_second_redirect(
    monkeypatch,
):
    issued_redirects = []
    reflected = _round10_reviewer_reflection()
    unsafe_query = "ref=" + reflected
    unsafe_intermediate = (
        "https://attacker.invalid/intermediate?" + unsafe_query
    )

    def opener_factory(*handlers):
        redirect_handler = next(
            handler
            for handler in handlers
            if isinstance(handler, source_fetcher._CredentialRedirectHandler)
        )

        class FixtureOpener:
            def open(self, request, timeout):
                first = redirect_handler.redirect_request(
                    request,
                    None,
                    302,
                    "Found",
                    {},
                    "https://redirect.example.invalid/safe-intermediate",
                )
                issued_redirects.append(first.full_url)
                second = redirect_handler.redirect_request(
                    first,
                    None,
                    302,
                    "Found",
                    {},
                    unsafe_intermediate,
                )
                issued_redirects.append(second.full_url)
                raise AssertionError("unsafe second redirect was issued")

        return FixtureOpener()

    monkeypatch.setattr(source_fetcher, "build_opener", opener_factory)

    with pytest.raises(SourceEvidenceError) as caught:
        source_fetcher._download(
            {
                "kind": "elsevier_article_api_xml",
                "url": "https://api.elsevier.com/content/article",
                "expected_media_type": "application/pdf",
            },
            object(),
            credential_profile=_round10_credential_profile(
                ROUND9_SPACED_SECRET
            ),
        )

    assert issued_redirects == [
        "https://redirect.example.invalid/safe-intermediate"
    ]
    _round10_assert_generic_rejection(
        caught,
        forbidden_values=(
            ROUND9_SPACED_SECRET,
            reflected,
            unsafe_query,
            unsafe_intermediate,
            *_round10_reference_form_stages(unsafe_query),
        ),
    )


def test_round10_depth_four_expanded_same_origin_secret_is_rejected():
    reflected = _round10_reviewer_reflection()
    target = (
        "https://api.elsevier.com/content/article?ref=" + reflected
    )

    with pytest.raises(SourceEvidenceError) as caught:
        _round10_redirect_handler().redirect_request(
            _round10_initial_request(),
            None,
            302,
            "Found",
            {},
            target,
        )

    _round10_assert_generic_rejection(
        caught,
        forbidden_values=(ROUND9_SPACED_SECRET, reflected, target),
    )


@pytest.mark.parametrize(
    ("secret", "reflected"),
    (
        pytest.param(
            ROUND9_SPACED_SECRET,
            ROUND9_SPACED_SECRET.replace(
                " ", _round10_expand_every_character("+", 4), 1
            )
            .replace(" ", "%25252B", 1)
            .replace(" ", "%25%32%42", 1),
            id="compact-expanded-mixed",
        ),
        pytest.param(
            ROUND9_SPACED_SECRET,
            ROUND9_SPACED_SECRET.replace(
                " ",
                _round10_expand_every_character(
                    "+", 4, lowercase_first=True
                ),
            ),
            id="mixed-hex-case-expanded",
        ),
        pytest.param(
            "Bearer TOKEN",
            "Bearer"
            + _round10_expand_every_character("+", 4)
            + "TOKEN",
            id="minimal-one-space-bearer-token",
        ),
    ),
)
def test_round10_ascii_compact_expanded_and_case_mixtures_are_rejected(
    secret,
    reflected,
):
    query = "ref=" + reflected
    assert _round10_reference_contains_secret(query, secret)

    with pytest.raises(SourceEvidenceError) as caught:
        _round10_redirect_handler(secret).redirect_request(
            _round10_initial_request(secret),
            None,
            302,
            "Found",
            {},
            "https://attacker.invalid/capture?" + query,
        )

    _round10_assert_generic_rejection(
        caught,
        forbidden_values=(secret, reflected, query),
    )


@pytest.mark.parametrize(
    ("secret", "preimage", "depth"),
    (
        pytest.param("TOKEN+42", quote_plus("TOKEN+42", safe=""), 5,
                     id="plus-secret-at-intermediate-stage"),
        pytest.param("A + B", quote_plus("A + B", safe=""), 5,
                     id="mixed-space-plus-intermediate-stage"),
        pytest.param("%41%42", "%2541%2542", 5,
                     id="percent-secret-at-intermediate-stage"),
        pytest.param("41", "%41", 6,
                     id="hex-only-secret-at-intermediate-stage"),
    ),
)
def test_round10_every_sensitive_intermediate_frontier_is_rejected(
    secret,
    preimage,
    depth,
):
    query = "value=" + _round10_expand_every_character(preimage, depth)
    stages = _round10_reference_form_stages(query)
    assert any(secret.casefold() in stage.casefold() for stage in stages)

    with pytest.raises(SourceEvidenceError) as caught:
        _round10_redirect_handler(secret).redirect_request(
            _round10_initial_request(secret),
            None,
            302,
            "Found",
            {},
            "https://attacker.invalid/capture?" + query,
        )

    _round10_assert_generic_rejection(
        caught,
        forbidden_values=(secret, query, *stages),
    )


@pytest.mark.parametrize(
    "query",
    (
        pytest.param("value=%C3%A9", id="valid-utf8-high-bytes"),
        pytest.param("value=%FF", id="invalid-utf8-high-byte"),
        pytest.param(
            "value=" + _round10_expand_every_character("%C3%A9", 4),
            id="deep-expanded-high-bytes",
        ),
    ),
)
def test_round10_percent_decoded_high_bytes_fail_closed_for_unicode_safe_semantics(
    query,
):
    secret = "credential-contains-\ufffd-but-is-not-in-query"

    with pytest.raises(SourceEvidenceError) as caught:
        _round10_redirect_handler(secret).redirect_request(
            _round10_initial_request(secret),
            None,
            302,
            "Found",
            {},
            "https://attacker.invalid/capture?" + query,
        )

    _round10_assert_generic_rejection(
        caught,
        forbidden_values=(secret, query),
    )


@pytest.mark.parametrize(
    "query",
    (
        pytest.param("value=distinct+signed", id="literal-plus"),
        pytest.param("value=distinct%2Bsigned", id="percent-plus"),
        pytest.param("value=distinct%20signed", id="percent-space"),
        pytest.param("value=malformed%GGescape", id="malformed-percent"),
        pytest.param("value=literal-é-safe", id="literal-unicode"),
    ),
)
def test_round10_unrelated_common_query_forms_remain_allowed(query):
    secret = "Authorization: Bearer OTHER 99"
    target = "https://attacker.invalid/download?" + query
    redirected = _round10_redirect_handler(secret).redirect_request(
        _round10_initial_request(secret),
        None,
        302,
        "Found",
        {},
        target,
    )

    assert redirected.full_url == target
    assert not _CREDENTIAL_HEADER_CASEFOLDS.intersection(
        _header_dict(redirected)
    )


def test_round10_different_active_secret_signed_query_remains_allowed():
    secret = "Authorization: Bearer DIFFERENT 99"
    query = (
        "signature=Authorization%3A+Bearer+TOKEN+42"
        "&ticket=distinct%2Bsigned%20value%252541"
    )
    assert not _round10_reference_contains_secret(query, secret)
    target = "https://attacker.invalid/download?" + query

    redirected = _round10_redirect_handler(secret).redirect_request(
        _round10_initial_request(secret),
        None,
        302,
        "Found",
        {},
        target,
    )

    assert redirected.full_url == target


def test_round10_unrelated_deep_expanded_ascii_token_remains_allowed():
    secret = ROUND9_SPACED_SECRET
    token = _round10_expand_every_character(
        quote_plus("distinct signed token", safe=""),
        6,
    )
    query = "signature=" + token
    assert len(query) < ROUND9_QUERY_LIMIT
    assert not _round10_reference_contains_secret(query, secret)
    target = "https://attacker.invalid/download?" + query

    redirected = _round10_redirect_handler(secret).redirect_request(
        _round10_initial_request(secret),
        None,
        302,
        "Found",
        {},
        target,
    )

    assert redirected.full_url == target


def test_round10_degenerate_compact_nesting_exhausts_work_and_fails_closed(
    monkeypatch,
):
    super_calls = []

    def forbidden_super(*args, **kwargs):
        super_calls.append((args, kwargs))
        raise AssertionError("redirect Request construction was reached")

    monkeypatch.setattr(
        source_fetcher.HTTPRedirectHandler,
        "redirect_request",
        forbidden_super,
    )
    prefix = "value="
    compact = "%2B"
    depth = (ROUND9_QUERY_LIMIT - len(prefix) - len(compact)) // 2
    compact = "%" + "25" * depth + compact[1:]
    query = prefix + compact
    assert len(query) <= ROUND9_QUERY_LIMIT
    assert depth > 8_000

    with pytest.raises(SourceEvidenceError) as caught:
        _round10_redirect_handler().redirect_request(
            _round10_initial_request(),
            None,
            302,
            "Found",
            {},
            "https://attacker.invalid/capture?" + query,
        )

    assert super_calls == []
    _round10_assert_generic_rejection(
        caught,
        forbidden_values=(ROUND9_SPACED_SECRET, query),
    )


def test_round10_path_literal_plus_stays_outside_form_normalization():
    secret = ROUND9_SPACED_SECRET
    path = "/capture/Authorization:+Bearer+TOKEN+42"
    query = "signature=" + _round10_expand_every_character("safe+token", 3)
    target = "https://attacker.invalid" + path + "?" + query

    redirected = _round10_redirect_handler(secret).redirect_request(
        _round10_initial_request(secret),
        None,
        302,
        "Found",
        {},
        target,
    )

    assert redirected.full_url == target


def test_round10_query_limit_is_checked_before_sensitive_scan_or_super(
    monkeypatch,
):
    contains_calls = []
    super_calls = []

    def forbidden_contains(*args, **kwargs):
        contains_calls.append((args, kwargs))
        raise AssertionError("sensitive scan was reached before the query cap")

    def forbidden_super(*args, **kwargs):
        super_calls.append((args, kwargs))
        raise AssertionError("redirect Request construction was reached")

    monkeypatch.setattr(source_fetcher, "_contains_sensitive", forbidden_contains)
    monkeypatch.setattr(
        source_fetcher.HTTPRedirectHandler,
        "redirect_request",
        forbidden_super,
    )
    query = "signature=" + "x" * (ROUND9_QUERY_LIMIT + 1 - len("signature="))
    assert len(query) == ROUND9_QUERY_LIMIT + 1

    with pytest.raises(SourceEvidenceError) as caught:
        _round10_redirect_handler().redirect_request(
            _round10_initial_request(),
            None,
            302,
            "Found",
            {},
            "https://attacker.invalid/download?" + query,
        )

    assert contains_calls == []
    assert super_calls == []
    _round10_assert_generic_rejection(
        caught,
        forbidden_values=(ROUND9_SPACED_SECRET, query),
    )


def test_round10_query_at_limit_continues_sensitive_checks(monkeypatch):
    calls = []
    original_contains = source_fetcher._contains_sensitive

    def recording_contains(*args, **kwargs):
        calls.append((args, kwargs))
        return original_contains(*args, **kwargs)

    monkeypatch.setattr(source_fetcher, "_contains_sensitive", recording_contains)
    query = "signature=" + "x" * (ROUND9_QUERY_LIMIT - len("signature="))
    target = "https://attacker.invalid/download?" + query

    redirected = _round10_redirect_handler().redirect_request(
        _round10_initial_request(),
        None,
        302,
        "Found",
        {},
        target,
    )

    assert calls
    assert redirected.full_url == target


def test_round10_systematic_and_random_ascii_matrix_matches_finite_reference():
    unsafe_cases = []
    for secret in (
        "Bearer TOKEN",
        "TOKEN+42",
        "A + B",
        "%41%42",
        "41",
    ):
        encoded = quote_plus(secret, safe="")
        for depth in range(3, 6):
            unsafe_cases.append(
                (secret, _round10_expand_every_character(encoded, depth))
            )

    generator = random.Random(1009)
    alphabet = "ABCDEFGH0123456789 +%"
    for _ in range(32):
        secret = "".join(
            generator.choice(alphabet)
            for _ in range(generator.randint(4, 10))
        ).strip()
        if not secret:
            secret = "A 1%"
        depth = generator.randint(3, 5)
        unsafe_cases.append(
            (
                secret,
                _round10_expand_every_character(
                    quote_plus(secret, safe=""),
                    depth,
                    lowercase_first=bool(generator.getrandbits(1)),
                ),
            )
        )

    for secret, reflected in unsafe_cases:
        query = "value=" + reflected
        assert _round10_reference_contains_secret(query, secret)
        with pytest.raises(SourceEvidenceError):
            _round10_redirect_handler(secret).redirect_request(
                _round10_initial_request(secret),
                None,
                302,
                "Found",
                {},
                "https://attacker.invalid/capture?" + query,
            )

    safe_checked = 0
    while safe_checked < 32:
        secret = "secret-" + "".join(
            generator.choice(alphabet)
            for _ in range(generator.randint(4, 10))
        )
        signed_value = "signed-" + "".join(
            generator.choice(alphabet.replace("%", ""))
            for _ in range(generator.randint(4, 10))
        )
        reflected = _round10_expand_every_character(
            quote_plus(signed_value, safe=""),
            generator.randint(2, 5),
            lowercase_first=bool(generator.getrandbits(1)),
        )
        query = "value=" + reflected
        if (
            len(query) > ROUND9_QUERY_LIMIT
            or _round10_reference_contains_secret(query, secret)
        ):
            continue
        target = "https://attacker.invalid/capture?" + query
        redirected = _round10_redirect_handler(secret).redirect_request(
            _round10_initial_request(secret),
            None,
            302,
            "Found",
            {},
            target,
        )
        assert redirected.full_url == target
        safe_checked += 1


ROUND11_CORE_SIDECAR_BYTES = json.dumps(
    _core_mg_work_identity_document(),
    sort_keys=True,
).encode("utf-8")


def _round11_replace_inline_sidecar_fingerprint(source_dir, payload):
    provenance_path = source_dir / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    descriptor = provenance["retrieval_metadata"]["work_identity_evidence"]
    descriptor["payload_sha256"] = hashlib.sha256(payload).hexdigest()
    descriptor["payload_byte_length"] = len(payload)
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("legacy", (False, True), ids=("core-new", "openalex-legacy"))
def test_round11_offline_json_sidecar_uses_exactly_one_path_read(
    tmp_path,
    monkeypatch,
    legacy,
):
    if legacy:
        source_dir, route = _repository_fixture(
            tmp_path,
            legacy_evidence_url=True,
        )
        source = _expected_source()
    else:
        source_dir, source, route, _descriptor = _special_sidecar_cache(
            tmp_path,
            "core_same_work_output",
        )
    sidecar_path = source_dir / "work-identity.json"
    real_open = Path.open
    sidecar_reads = []

    def one_read_only(path, mode="r", *args, **kwargs):
        if path == sidecar_path and "r" in mode:
            sidecar_reads.append(mode)
            if len(sidecar_reads) > 1:
                raise AssertionError("JSON sidecar path was read twice")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", one_read_only)

    verified = load_verified_source(
        source_dir,
        expected_source=source,
        provisioning_route=route,
    )

    assert verified.source_id == source["source_id"]
    assert sidecar_reads == ["rb"]


def test_round11_invalid_hashed_snapshot_cannot_be_replaced_by_valid_second_read(
    tmp_path,
    monkeypatch,
):
    source_dir, source, route, _descriptor = _special_sidecar_cache(
        tmp_path,
        "core_same_work_output",
    )
    sidecar_path = source_dir / "work-identity.json"
    hashed_snapshot = b"{"
    later_snapshot = ROUND11_CORE_SIDECAR_BYTES
    _round11_replace_inline_sidecar_fingerprint(source_dir, hashed_snapshot)
    real_read_bytes = Path.read_bytes
    validator_documents = []

    def swapping_read(path):
        if path == sidecar_path:
            sidecar_path.write_bytes(later_snapshot)
            return hashed_snapshot
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", swapping_read)
    monkeypatch.setattr(
        evidence_sources,
        "validate_work_identity_document",
        lambda document, **kwargs: validator_documents.append(document),
    )

    with pytest.raises(SourceEvidenceError, match="JSON") as caught:
        load_verified_source(
            source_dir,
            expected_source=source,
            provisioning_route=route,
        )

    assert validator_documents == []
    assert hashed_snapshot.decode("utf-8") not in str(caught.value)
    assert later_snapshot.decode("utf-8") not in str(caught.value)


def test_round11_valid_hashed_snapshot_ignores_invalid_later_path_contents(
    tmp_path,
    monkeypatch,
):
    source_dir, source, route, _descriptor = _special_sidecar_cache(
        tmp_path,
        "core_same_work_output",
    )
    sidecar_path = source_dir / "work-identity.json"
    later_snapshot = b"{"
    real_read_bytes = Path.read_bytes
    real_validate = evidence_sources.validate_work_identity_document
    validator_documents = []

    def swapping_read(path):
        if path == sidecar_path:
            sidecar_path.write_bytes(later_snapshot)
            return ROUND11_CORE_SIDECAR_BYTES
        return real_read_bytes(path)

    def recording_validate(document, **kwargs):
        validator_documents.append(document)
        return real_validate(document, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", swapping_read)
    monkeypatch.setattr(
        evidence_sources,
        "validate_work_identity_document",
        recording_validate,
    )

    verified = load_verified_source(
        source_dir,
        expected_source=source,
        provisioning_route=route,
    )

    assert verified.source_id == source["source_id"]
    assert validator_documents == [_core_mg_work_identity_document()]


@pytest.mark.parametrize(
    "payload",
    (
        pytest.param(b'{"LEAKY_KEY": 1, "LEAKY_KEY": 2}', id="duplicate-key"),
        pytest.param(b'{"value": NaN}', id="nan"),
        pytest.param(b'{"value": Infinity}', id="positive-infinity"),
        pytest.param(b'{"value": -Infinity}', id="negative-infinity"),
        pytest.param(b'{"value": "\xff"}', id="invalid-utf8"),
        pytest.param(b'{"value":', id="malformed-json"),
    ),
)
def test_round11_strict_json_bytes_parser_rejects_invalid_payloads_without_content(
    payload,
):
    with pytest.raises(SourceEvidenceError) as caught:
        evidence_sources._load_json_bytes(
            payload,
            context="work identity evidence JSON",
        )

    rendered = str(caught.value)
    assert "LEAKY_KEY" not in rendered
    assert payload.decode("utf-8", errors="ignore") not in rendered


@pytest.mark.parametrize(
    ("payload", "expected"),
    (
        pytest.param(b'{"value": [1, 2]}', {"value": [1, 2]}, id="mapping"),
        pytest.param(b'[1, {"value": 2}]', [1, {"value": 2}], id="list"),
        pytest.param(b'"scalar"', "scalar", id="string"),
        pytest.param(b'null', None, id="null"),
    ),
)
def test_round11_strict_json_bytes_parser_preserves_valid_top_levels(
    payload,
    expected,
):
    assert evidence_sources._load_json_bytes(
        payload,
        context="fixture JSON",
    ) == expected


def test_round11_path_json_loader_reads_once_and_delegates_to_bytes_parser(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "fixture.json"
    payload = b'{"fixture": true}'
    path.write_bytes(payload)
    calls = []
    sentinel = {"delegated": True}

    def bytes_loader(value, *, context):
        calls.append((value, context))
        return sentinel

    monkeypatch.setattr(
        evidence_sources,
        "_load_json_bytes",
        bytes_loader,
        raising=False,
    )

    assert evidence_sources._load_json(path) is sentinel
    assert calls == [(payload, f"provenance JSON {path}")]


def test_round11_sidecar_hash_and_length_precede_json_parse_and_validation(
    tmp_path,
    monkeypatch,
):
    source_dir, source, route, _descriptor = _special_sidecar_cache(
        tmp_path,
        "core_same_work_output",
    )
    sidecar_path = source_dir / "work-identity.json"
    events = []

    class TrackedPayload(bytes):
        def __len__(self):
            events.append("length")
            return super().__len__()

    payload = TrackedPayload(ROUND11_CORE_SIDECAR_BYTES)
    real_read_bytes = Path.read_bytes
    real_sha256 = evidence_sources.hashlib.sha256
    real_load_json_bytes = evidence_sources._load_json_bytes
    real_validate = evidence_sources.validate_work_identity_document

    def tracked_read(path):
        if path == sidecar_path:
            return payload
        return real_read_bytes(path)

    def tracked_sha256(value, *args, **kwargs):
        if value is payload:
            events.append("sha256")
        return real_sha256(value, *args, **kwargs)

    def tracked_json_parse(value, *, context):
        if value is payload:
            events.append("json-parse")
            return _core_mg_work_identity_document()
        return real_load_json_bytes(value, context=context)

    def tracked_validate(document, **kwargs):
        events.append("validate")
        return real_validate(document, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", tracked_read)
    monkeypatch.setattr(evidence_sources.hashlib, "sha256", tracked_sha256)
    monkeypatch.setattr(
        evidence_sources,
        "_load_json_bytes",
        tracked_json_parse,
        raising=False,
    )
    monkeypatch.setattr(
        evidence_sources,
        "validate_work_identity_document",
        tracked_validate,
    )

    load_verified_source(
        source_dir,
        expected_source=source,
        provisioning_route=route,
    )

    parse_index = events.index("json-parse")
    assert events.index("sha256") < parse_index
    assert all(
        index < parse_index
        for index, event in enumerate(events)
        if event == "length"
    )
    assert events.index("validate") > parse_index


def test_round11_resume_verifies_json_sidecar_once_without_network_or_writes(
    tmp_path,
    monkeypatch,
):
    source_dir, source, route, _descriptor = _special_sidecar_cache(
        tmp_path,
        "core_same_work_output",
    )
    before = _round7_tree_snapshot(source_dir)
    forbidden_events = _round7_forbid_resume_supplement(monkeypatch)
    sidecar_path = source_dir / "work-identity.json"
    real_open = Path.open
    sidecar_reads = []

    def one_read_only(path, mode="r", *args, **kwargs):
        if path == sidecar_path and "r" in mode:
            sidecar_reads.append(mode)
            if len(sidecar_reads) > 1:
                raise AssertionError("resume read JSON sidecar twice")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", one_read_only)

    outcome = source_fetcher._fetch_source(
        tmp_path,
        source,
        route,
        ca_bundle=Path("/unused"),
        resume=True,
    )

    assert outcome == {
        "source_id": source["source_id"],
        "status": "resumed",
        "detail": "existing cache verified",
    }
    assert forbidden_events == []
    assert sidecar_reads == ["rb"]
    monkeypatch.undo()
    assert _round7_tree_snapshot(source_dir) == before


def test_round11_new_json_sidecar_write_immediately_replays_one_snapshot(
    tmp_path,
    monkeypatch,
):
    fixture = _round7_signed_sidecar_roundtrip_fixture(
        "core_same_work_output"
    )
    source = fixture["source"]
    route = fixture["route"]
    source_dir = tmp_path / source["source_id"]
    sidecar_path = source_dir / "work-identity.json"
    primary_final_url = route["authoritative_retrieval_route"]["url"]
    real_open = Path.open
    sidecar_reads = []

    class FixtureOpener:
        def open(self, request, timeout):
            accept = _header_dict(request).get("accept")
            if accept == "application/pdf":
                return _FixtureHTTPResponse(
                    fixture["primary_payload"],
                    content_type="application/pdf",
                    final_url=primary_final_url,
                )
            return _FixtureHTTPResponse(
                fixture["sidecar_payload"],
                content_type="application/json",
                final_url=fixture["sidecar_final_url"],
            )

    def one_read_only(path, mode="r", *args, **kwargs):
        if path == sidecar_path and "r" in mode:
            sidecar_reads.append(mode)
            if len(sidecar_reads) > 1:
                raise AssertionError("immediate replay read JSON sidecar twice")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(source_fetcher, "_ssl_context", lambda path: object())
    monkeypatch.setattr(
        source_fetcher,
        "_fetch_bibliographic_metadata",
        lambda *args, **kwargs: dict(fixture["bibliographic"]),
    )
    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )
    monkeypatch.setattr(Path, "open", one_read_only)

    outcome = source_fetcher._fetch_source(
        tmp_path,
        source,
        route,
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert outcome["status"] == "acquired"
    assert sidecar_reads == ["rb"]


def test_round11_invalid_downloaded_json_sidecar_fails_before_any_cache_write(
    tmp_path,
    monkeypatch,
):
    fixture = _round7_signed_sidecar_roundtrip_fixture(
        "core_same_work_output"
    )
    source = fixture["source"]
    route = fixture["route"]
    source_dir = tmp_path / source["source_id"]

    class FixtureOpener:
        def open(self, request, timeout):
            accept = _header_dict(request).get("accept")
            if accept == "application/pdf":
                return _FixtureHTTPResponse(
                    fixture["primary_payload"],
                    content_type="application/pdf",
                    final_url=route["authoritative_retrieval_route"]["url"],
                )
            return _FixtureHTTPResponse(
                b"{",
                content_type="application/json",
                final_url=fixture["sidecar_final_url"],
            )

    monkeypatch.setattr(source_fetcher, "_ssl_context", lambda path: object())
    monkeypatch.setattr(
        source_fetcher,
        "_fetch_bibliographic_metadata",
        lambda *args, **kwargs: dict(fixture["bibliographic"]),
    )
    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )

    outcome = source_fetcher._fetch_source(
        tmp_path,
        source,
        route,
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert outcome["status"] == "failed"
    assert not source_dir.exists()


ROUND12_JSON_ACQUISITION_KINDS = (
    "core_same_work_output",
    "openalex_same_work_location",
)


def _round12_json_acquisition_fixture(evidence_kind):
    if evidence_kind == "core_same_work_output":
        fixture = _round7_signed_sidecar_roundtrip_fixture(evidence_kind)
        return {
            **fixture,
            "sidecar_document": json.loads(
                fixture["sidecar_payload"].decode("utf-8")
            ),
        }
    if evidence_kind != "openalex_same_work_location":
        raise AssertionError(f"unknown JSON evidence kind {evidence_kind}")

    doi = "10.1016/j.aop.2005.10.005"
    arxiv_id = "cond-mat/0506438"
    identity = {"kind": "doi", "value": doi}
    route_spec = authoritative_route_for_identity(identity)
    source_id = "doi_" + hashlib.sha256(
        f"doi:{doi}".encode("ascii")
    ).hexdigest()[:20]
    sidecar_document = {
        "id": "https://openalex.org/W2141708961",
        "doi": f"https://doi.org/{doi}",
        "locations": [
            {"pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf"}
        ],
    }
    return {
        "source": {
            "source_id": source_id,
            "canonical_identity": identity,
            "canonical_url": f"https://doi.org/{doi}",
            "benchmark_names": ["round12_openalex_acquisition_fixture"],
        },
        "route": {
            "source_id": source_id,
            "authoritative_retrieval_route": route_spec,
            "expected_media_type": "application/pdf",
            "access_mode": "unattended",
            "local_cache_location": f"source-cache/{source_id}/source.pdf",
        },
        "bibliographic": {
            "title": "Round twelve OpenAlex acquisition fixture",
            "authors": ["Fixture Author"],
            "venue": "Annals of Physics",
            "publication_date": "2006-01-01",
        },
        "primary_payload": _minimal_pdf(
            "Round twelve legacy OpenAlex acquisition fixture."
        ),
        "sidecar_document": sidecar_document,
        "sidecar_payload": json.dumps(
            sidecar_document,
            sort_keys=True,
        ).encode("utf-8"),
        "sidecar_media_type": "application/json",
        "sidecar_final_url": route_spec["work_identity_evidence"]["url"],
    }


def _round12_invalid_json_sidecar(valid_payload, mutation):
    assert valid_payload.startswith(b"{")
    injected = {
        "duplicate-key": (
            b'"ROUND12_DUPLICATE_KEY":1,',
            b'"ROUND12_DUPLICATE_KEY":2,'
        ),
        "nan": (b'"ROUND12_NONFINITE_NAN":NaN,',),
        "positive-infinity": (
            b'"ROUND12_NONFINITE_POSITIVE_INFINITY":Infinity,',
        ),
        "negative-infinity": (
            b'"ROUND12_NONFINITE_NEGATIVE_INFINITY":-Infinity,',
        ),
    }
    if mutation in injected:
        fragments = injected[mutation]
        payload = b"{" + b"".join(fragments) + valid_payload[1:]
        marker = fragments[0].split(b'"', 2)[1].decode("ascii")
        return payload, marker
    if mutation == "invalid-utf8":
        return b'{"ROUND12_INVALID_UTF8":"\xff"}', "ROUND12_INVALID_UTF8"
    if mutation == "malformed-json":
        return (
            b'{"ROUND12_MALFORMED_DOCUMENT":"ROUND12_DOCUMENT_CONTENT"',
            "ROUND12_DOCUMENT_CONTENT",
        )
    raise AssertionError(f"unknown strict-JSON mutation {mutation}")


def _round12_install_json_acquisition_boundary(
    monkeypatch,
    fixture,
    sidecar_payload,
):
    requests = []

    class FixtureOpener:
        def open(self, request, timeout):
            accept = _header_dict(request).get("accept")
            requests.append((request.full_url, accept, timeout))
            if accept == "application/pdf":
                return _FixtureHTTPResponse(
                    fixture["primary_payload"],
                    content_type="application/pdf",
                    final_url=fixture["route"][
                        "authoritative_retrieval_route"
                    ]["url"],
                )
            assert accept == "application/json"
            return _FixtureHTTPResponse(
                sidecar_payload,
                content_type="application/json",
                final_url=fixture["sidecar_final_url"],
            )

    monkeypatch.setattr(source_fetcher, "_ssl_context", lambda path: object())
    monkeypatch.setattr(
        source_fetcher,
        "_fetch_bibliographic_metadata",
        lambda *args, **kwargs: dict(fixture["bibliographic"]),
    )
    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )
    return requests


@pytest.mark.parametrize(
    "evidence_kind",
    ROUND12_JSON_ACQUISITION_KINDS,
    ids=("core-new", "openalex-legacy"),
)
@pytest.mark.parametrize(
    "mutation",
    (
        "duplicate-key",
        "nan",
        "positive-infinity",
        "negative-infinity",
        "invalid-utf8",
        "malformed-json",
    ),
)
def test_round12_strict_invalid_json_acquisition_fails_before_cache_write(
    tmp_path,
    monkeypatch,
    evidence_kind,
    mutation,
):
    fixture = _round12_json_acquisition_fixture(evidence_kind)
    payload, marker = _round12_invalid_json_sidecar(
        fixture["sidecar_payload"],
        mutation,
    )
    source = fixture["source"]
    source_dir = tmp_path / source["source_id"]
    validator_documents = []
    cache_file_writes = []
    real_validate = source_fetcher.validate_work_identity_document
    real_path_open = Path.open

    def recording_validate(document, **kwargs):
        validator_documents.append(document)
        return real_validate(document, **kwargs)

    def recording_path_open(path, mode="r", *args, **kwargs):
        try:
            relative_path = path.relative_to(source_dir)
        except ValueError:
            relative_path = None
        if relative_path is not None and any(flag in mode for flag in "wax+"):
            cache_file_writes.append((relative_path.as_posix(), mode))
        return real_path_open(path, mode, *args, **kwargs)

    requests = _round12_install_json_acquisition_boundary(
        monkeypatch,
        fixture,
        payload,
    )
    monkeypatch.setattr(
        source_fetcher,
        "validate_work_identity_document",
        recording_validate,
    )
    monkeypatch.setattr(Path, "open", recording_path_open)

    outcome = source_fetcher._fetch_source(
        tmp_path,
        source,
        fixture["route"],
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert outcome["status"] == "failed"
    assert [accept for _url, accept, _timeout in requests] == [
        "application/pdf",
        "application/json",
    ]
    assert validator_documents == []
    assert not source_dir.exists()
    assert cache_file_writes == []
    assert outcome["detail"] == (
        f"new cache directory {source_dir} failed: "
        "work identity evidence JSON is not valid strict JSON"
    )
    rendered = json.dumps(outcome, sort_keys=True)
    assert marker not in rendered
    assert payload.decode("utf-8", errors="ignore") not in rendered


@pytest.mark.parametrize(
    "evidence_kind",
    ROUND12_JSON_ACQUISITION_KINDS,
    ids=("core-new", "openalex-legacy"),
)
def test_round12_valid_json_acquisition_control(
    tmp_path,
    monkeypatch,
    evidence_kind,
):
    fixture = _round12_json_acquisition_fixture(evidence_kind)
    validator_documents = []
    real_validate = source_fetcher.validate_work_identity_document

    def recording_validate(document, **kwargs):
        validator_documents.append(document)
        return real_validate(document, **kwargs)

    requests = _round12_install_json_acquisition_boundary(
        monkeypatch,
        fixture,
        fixture["sidecar_payload"],
    )
    monkeypatch.setattr(
        source_fetcher,
        "validate_work_identity_document",
        recording_validate,
    )

    outcome = source_fetcher._fetch_source(
        tmp_path,
        fixture["source"],
        fixture["route"],
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert outcome["status"] == "acquired"
    assert [accept for _url, accept, _timeout in requests] == [
        "application/pdf",
        "application/json",
    ]
    assert validator_documents == [fixture["sidecar_document"]]
    assert (tmp_path / fixture["source"]["source_id"]).is_dir()


# Task 5A.1 mutation-first contracts.  The common install lifecycle uses the
# exact HAL/Garel route and response bytes; dedicated CORE ordering contracts
# remain below for Task 5A.3.


def _task5a_hal_lifecycle_pdf_payload():
    rendered = " ".join(TASK5A_GAREL_PDF_TEXT.split())
    payload = _minimal_pdf(rendered)
    font_marker = b"BT /F1 12 Tf"
    assert payload.count(font_marker) == 1
    return payload.replace(font_marker, b"BT /F1 04 Tf", 1)


def _task5a_lifecycle_fixture():
    source_id = "doi_dba239926d673e54f80a"
    source = {
        "source_id": source_id,
        "canonical_identity": copy.deepcopy(TASK5A_GAREL_IDENTITY),
        "canonical_url": (
            "https://doi.org/" + TASK5A_GAREL_IDENTITY["value"]
        ),
        "benchmark_names": ["task5a_hal_garel_lifecycle_fixture"],
    }
    authoritative_route = {
        "kind": "author_repository_pdf",
        "url": (
            "https://www.lptmc.jussieu.fr/files/maillard/PUB2/"
            "Frustrated_jav16i10p2257.pdf"
        ),
        "expected_media_type": "application/pdf",
        "access_mode": "unattended",
        "artifact_identifier": (
            "author-repository:Frustrated_jav16i10p2257.pdf"
        ),
        "work_identity_evidence": {
            "kind": "hal_same_work_bibliographic_payload",
            "url": TASK5A_HAL_BASE,
            "record_identifier": TASK5A_HAL_STABLE_ID,
            "stable_document_url": TASK5A_HAL_STABLE_URL,
        },
    }
    route = {
        "source_id": source_id,
        "authoritative_retrieval_route": authoritative_route,
        "expected_media_type": "application/pdf",
        "access_mode": "unattended",
        "local_cache_location": f"source-cache/{source_id}/source.pdf",
    }
    sidecar_document = _task5a_hal_document()
    sidecar_payload = json.dumps(
        sidecar_document,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    assert evidence_sources._load_json_bytes(
        sidecar_payload,
        context="Task 5A HAL lifecycle fixture",
    ) == sidecar_document
    sidecar_descriptor = {
        "kind": "hal_same_work_bibliographic_payload",
        "url": TASK5A_HAL_BASE,
        "document_base_url": TASK5A_HAL_STABLE_URL,
        "media_type": "application/json",
        "payload_relative_path": "work-identity.json",
        "payload_sha256": hashlib.sha256(sidecar_payload).hexdigest(),
        "payload_byte_length": len(sidecar_payload),
    }
    return {
        "source": source,
        "route": route,
        "bibliographic": copy.deepcopy(TASK5A_GAREL_CROSSREF),
        "primary_payload": _task5a_hal_lifecycle_pdf_payload(),
        "sidecar_document": sidecar_document,
        "sidecar_payload": sidecar_payload,
        "sidecar_media_type": "application/json",
        "sidecar_final_url": TASK5A_HAL_REQUEST_URL,
        "sidecar_descriptor": sidecar_descriptor,
    }


def _task5a_cache_manifest(cache_root):
    cache_root = Path(cache_root)
    if not cache_root.exists():
        return ()
    manifest = []
    for path in sorted(cache_root.rglob("*")):
        relative = path.relative_to(cache_root).as_posix()
        status = path.lstat()
        if path.is_symlink():
            manifest.append((relative, "symlink", status.st_mode, os.readlink(path)))
        elif path.is_file():
            manifest.append((relative, "file", status.st_mode, path.read_bytes()))
        else:
            manifest.append((relative, "directory", status.st_mode, None))
    return tuple(manifest)


def _task5a_assert_complete_hal_candidate(candidate, fixture):
    candidate = Path(candidate)
    assert candidate.joinpath("source.pdf").read_bytes() == fixture[
        "primary_payload"
    ]
    assert candidate.joinpath("provenance.json").is_file()
    assert candidate.joinpath("work-identity.json").read_bytes() == fixture[
        "sidecar_payload"
    ]
    descriptor_path = candidate / "work-identity.provenance.json"
    assert json.loads(descriptor_path.read_text(encoding="utf-8")) == fixture[
        "sidecar_descriptor"
    ]
    serialized_provenance = candidate.joinpath("provenance.json").read_text(
        encoding="utf-8"
    )
    assert TASK5A_HAL_QUERY not in serialized_provenance
    assert TASK5A_HAL_REQUEST_URL not in serialized_provenance


def _task5a_install_real_lifecycle_boundary(
    monkeypatch,
    fixture,
    *,
    events,
    target=None,
    target_visibility=None,
    sidecar_payload=None,
    bibliographic=None,
    primary_content_type="application/pdf",
):
    sidecar_payload = (
        fixture["sidecar_payload"]
        if sidecar_payload is None
        else sidecar_payload
    )
    bibliographic = (
        fixture["bibliographic"]
        if bibliographic is None
        else bibliographic
    )
    real_primary_validator = source_fetcher.validate_download_response
    real_live_validator = source_fetcher.validate_work_identity_document
    real_offline_validator = evidence_sources.validate_work_identity_document

    def record_event(name):
        events.append(name)
        if target is not None and target_visibility is not None:
            target_visibility.append(
                (name, target.exists() or target.is_symlink())
            )

    class FixtureOpener:
        def open(self, request, timeout):
            accept = _header_dict(request).get("accept")
            if accept == "application/pdf":
                record_event("primary-response-bytes")
                return _FixtureHTTPResponse(
                    fixture["primary_payload"],
                    content_type=primary_content_type,
                    final_url=fixture["route"][
                        "authoritative_retrieval_route"
                    ]["url"],
                )
            assert accept == "application/json"
            record_event("hal-raw-sidecar-response-bytes")
            return _FixtureHTTPResponse(
                sidecar_payload,
                content_type="application/json",
                final_url=fixture["sidecar_final_url"],
            )

    def fetch_bibliographic(*args, **kwargs):
        record_event("crossref-bibliographic-metadata")
        return copy.deepcopy(bibliographic)

    def primary_validator(*args, **kwargs):
        result = real_primary_validator(*args, **kwargs)
        record_event("primary-response-media-validated")
        return result

    def live_validator(document, **kwargs):
        record_event("live-hal-crossref-validator-enter")
        result = real_live_validator(document, **kwargs)
        record_event("live-hal-crossref-validator-complete")
        return result

    def offline_validator(document, **kwargs):
        record_event("offline-hal-crossref-validator-enter")
        result = real_offline_validator(document, **kwargs)
        record_event("offline-hal-crossref-validator-complete")
        return result

    monkeypatch.setattr(source_fetcher, "_ssl_context", lambda _path: object())
    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )
    monkeypatch.setattr(
        source_fetcher,
        "_fetch_bibliographic_metadata",
        fetch_bibliographic,
    )
    monkeypatch.setattr(
        source_fetcher,
        "validate_download_response",
        primary_validator,
    )
    monkeypatch.setattr(
        source_fetcher,
        "validate_work_identity_document",
        live_validator,
    )
    monkeypatch.setattr(
        evidence_sources,
        "validate_work_identity_document",
        offline_validator,
    )


def _task5a_assert_event_order(events, *ordered_events):
    assert all(events.count(event) == 1 for event in ordered_events), events
    positions = [events.index(event) for event in ordered_events]
    assert positions == sorted(positions), events


def _task5a_assert_inputs_complete_before(events, terminal_event):
    prerequisites = (
        "primary-response-bytes",
        "primary-response-media-validated",
        "crossref-bibliographic-metadata",
        "hal-raw-sidecar-response-bytes",
        "live-hal-crossref-validator-enter",
        "live-hal-crossref-validator-complete",
    )
    assert events.count(terminal_event) == 1, events
    assert all(events.count(event) == 1 for event in prerequisites), events
    terminal_position = events.index(terminal_event)
    assert all(events.index(event) < terminal_position for event in prerequisites), events
    _task5a_assert_event_order(
        events,
        "hal-raw-sidecar-response-bytes",
        "live-hal-crossref-validator-enter",
        "live-hal-crossref-validator-complete",
    )


@pytest.mark.parametrize(
    "failure_stage",
    (
        "primary-response-media",
        "crossref-metadata",
        "raw-sidecar-validation",
        "hal-crossref-agreement",
        "provenance-build",
        "exclusive-payload-write",
        "provenance-serialization",
        "exclusive-sidecar-write",
        "offline-candidate-replay",
    ),
)
def test_task5a_candidate_failure_at_every_stage_never_exposes_target_or_mutates_tree(
    tmp_path,
    monkeypatch,
    failure_stage,
):
    cache_root = tmp_path / "source-cache"
    existing = cache_root / "preexisting_source"
    existing.mkdir(parents=True)
    existing.joinpath("source.pdf").write_bytes(b"PREEXISTING-BYTES")
    before = _task5a_cache_manifest(cache_root)
    fixture = _task5a_lifecycle_fixture()
    source = fixture["source"]
    route = fixture["route"]
    target = cache_root / source["source_id"]
    failure = SourceEvidenceError(f"injected {failure_stage} failure")
    events = []
    target_visibility = []
    sidecar_payload = fixture["sidecar_payload"]
    bibliographic = fixture["bibliographic"]
    primary_content_type = "application/pdf"

    if failure_stage == "primary-response-media":
        primary_content_type = "text/html"
    elif failure_stage == "raw-sidecar-validation":
        sidecar_payload, _marker = _round12_invalid_json_sidecar(
            sidecar_payload,
            "duplicate-key",
        )
    elif failure_stage == "hal-crossref-agreement":
        bibliographic = copy.deepcopy(bibliographic)
        bibliographic["title"] = "A different HAL work"

    _task5a_install_real_lifecycle_boundary(
        monkeypatch,
        fixture,
        events=events,
        target=target,
        target_visibility=target_visibility,
        sidecar_payload=sidecar_payload,
        bibliographic=bibliographic,
        primary_content_type=primary_content_type,
    )

    if failure_stage == "crossref-metadata":
        def fail_crossref_metadata(*args, **kwargs):
            events.append("crossref-bibliographic-metadata-failure")
            raise failure

        monkeypatch.setattr(
            source_fetcher,
            "_fetch_bibliographic_metadata",
            fail_crossref_metadata,
        )
    elif failure_stage == "provenance-build":
        def fail_provenance_build(*args, **kwargs):
            events.append("provenance-build-enter")
            raise failure

        monkeypatch.setattr(
            source_fetcher,
            "_build_provenance",
            fail_provenance_build,
        )
    elif failure_stage == "exclusive-payload-write":
        real_open = Path.open

        def fail_candidate_payload(path, mode="r", *args, **kwargs):
            if path.name == "source.pdf" and "x" in mode:
                events.append("exclusive-payload-write-enter")
                raise failure
            return real_open(path, mode, *args, **kwargs)

        monkeypatch.setattr(Path, "open", fail_candidate_payload)
    elif failure_stage == "provenance-serialization":
        def fail_provenance_serialization(*args, **kwargs):
            events.append("provenance-serialization-enter")
            raise failure

        monkeypatch.setattr(
            source_fetcher.json,
            "dump",
            fail_provenance_serialization,
        )
    elif failure_stage == "exclusive-sidecar-write":
        real_open = Path.open

        def fail_candidate_sidecar(path, mode="r", *args, **kwargs):
            if path.name == "work-identity.json" and "x" in mode:
                events.append("exclusive-sidecar-write-enter")
                raise failure
            return real_open(path, mode, *args, **kwargs)

        monkeypatch.setattr(Path, "open", fail_candidate_sidecar)
    elif failure_stage == "offline-candidate-replay":
        real_read_bytes = Path.read_bytes
        real_loader = source_fetcher.load_verified_source

        def replay_candidate(candidate, **kwargs):
            events.append("offline-replay-enter")
            return real_loader(candidate, **kwargs)

        def corrupt_candidate_payload_read(path):
            data = real_read_bytes(path)
            if path.name == "source.pdf" and path.parent != existing:
                events.append("offline-primary-payload-read")
                return data + b"INJECTED-OFFLINE-REPLAY-MUTATION"
            return data

        monkeypatch.setattr(source_fetcher, "load_verified_source", replay_candidate)
        monkeypatch.setattr(Path, "read_bytes", corrupt_candidate_payload_read)

    outcome = source_fetcher._fetch_source(
        cache_root,
        source,
        route,
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert outcome["status"] == "failed", outcome
    if failure_stage == "primary-response-media":
        assert "primary-response-bytes" in events
        assert "primary-response-media-validated" not in events
        assert "media type" in outcome["detail"]
    elif failure_stage == "crossref-metadata":
        assert "crossref-bibliographic-metadata-failure" in events
        assert str(failure) in outcome["detail"]
    elif failure_stage == "raw-sidecar-validation":
        assert "hal-raw-sidecar-response-bytes" in events
        assert "live-hal-crossref-validator-enter" not in events
        assert "strict JSON" in outcome["detail"]
    elif failure_stage == "hal-crossref-agreement":
        assert "live-hal-crossref-validator-enter" in events
        assert "live-hal-crossref-validator-complete" not in events
        assert "title" in outcome["detail"]
    else:
        terminal_event = {
            "provenance-build": "provenance-build-enter",
            "exclusive-payload-write": "exclusive-payload-write-enter",
            "provenance-serialization": "provenance-serialization-enter",
            "exclusive-sidecar-write": "exclusive-sidecar-write-enter",
            "offline-candidate-replay": "offline-replay-enter",
        }[failure_stage]
        _task5a_assert_inputs_complete_before(events, terminal_event)
        if failure_stage != "offline-candidate-replay":
            assert str(failure) in outcome["detail"]
    if failure_stage == "offline-candidate-replay":
        _task5a_assert_event_order(
            events,
            "offline-replay-enter",
            "offline-hal-crossref-validator-enter",
            "offline-hal-crossref-validator-complete",
            "offline-primary-payload-read",
        )
        assert "payload SHA-256" in outcome["detail"]
    assert not target.exists() and not target.is_symlink()
    assert not any(visible for _event, visible in target_visibility)
    assert _task5a_cache_manifest(cache_root) == before


def test_task5a_success_publishes_complete_target_only_after_real_offline_replay(
    tmp_path,
    monkeypatch,
):
    cache_root = tmp_path / "source-cache"
    existing = cache_root / "preexisting_source"
    existing.mkdir(parents=True)
    existing.joinpath("sentinel").write_bytes(b"UNCHANGED")
    foreign_staging = cache_root / ".foreign-operation-staging"
    foreign_staging.mkdir()
    foreign_staging.joinpath("sentinel").write_bytes(b"FOREIGN-STAGING")
    before_existing = _task5a_cache_manifest(existing)
    before_foreign_staging = _task5a_cache_manifest(foreign_staging)
    fixture = _task5a_lifecycle_fixture()
    source = fixture["source"]
    route = fixture["route"]
    target = cache_root / source["source_id"]
    events = []
    target_visibility = []
    replayed = []
    _task5a_install_real_lifecycle_boundary(
        monkeypatch,
        fixture,
        events=events,
        target=target,
        target_visibility=target_visibility,
    )
    real_loader = source_fetcher.load_verified_source

    def replay_candidate(candidate, **kwargs):
        candidate = Path(candidate)
        events.append("offline-replay-enter")
        target_visible_before_replay = target.exists() or target.is_symlink()
        _task5a_assert_complete_hal_candidate(candidate, fixture)
        verified = real_loader(candidate, **kwargs)
        events.append("offline-replay-complete")
        assert candidate != target
        assert candidate.parent == cache_root
        assert target_visible_before_replay is False
        assert candidate.joinpath("source.pdf").is_file()
        assert candidate.joinpath("provenance.json").is_file()
        assert candidate.joinpath("work-identity.json").is_file()
        assert candidate.joinpath("work-identity.provenance.json").is_file()
        assert not target.exists() and not target.is_symlink()
        replayed.append(verified)
        return verified

    monkeypatch.setattr(source_fetcher, "load_verified_source", replay_candidate)

    outcome = source_fetcher._fetch_source(
        cache_root,
        source,
        route,
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert outcome["status"] == "acquired", outcome
    _task5a_assert_inputs_complete_before(events, "offline-replay-enter")
    _task5a_assert_event_order(
        events,
        "offline-replay-enter",
        "offline-hal-crossref-validator-enter",
        "offline-hal-crossref-validator-complete",
        "offline-replay-complete",
    )
    assert len(replayed) == 1
    assert replayed[0].source_id == source["source_id"]
    assert not any(visible for _event, visible in target_visibility)
    assert target.is_dir() and not target.is_symlink()
    assert {path.name for path in cache_root.iterdir()} == {
        ".foreign-operation-staging",
        "preexisting_source",
        source["source_id"],
    }
    assert _task5a_cache_manifest(existing) == before_existing
    assert _task5a_cache_manifest(foreign_staging) == before_foreign_staging


@pytest.mark.parametrize("collision_kind", ("empty", "nonempty"))
def test_task5a_concurrent_target_collision_never_enters_replaces_or_modifies_target(
    tmp_path,
    monkeypatch,
    collision_kind,
):
    cache_root = tmp_path / "source-cache"
    cache_root.mkdir()
    existing = cache_root / "preexisting_source"
    existing.mkdir()
    existing.joinpath("sentinel").write_bytes(b"PREEXISTING-BYTES")
    foreign_staging = cache_root / ".foreign-operation-staging"
    foreign_staging.mkdir()
    foreign_staging.joinpath("sentinel").write_bytes(b"FOREIGN-STAGING")
    before_existing = _task5a_cache_manifest(existing)
    before_foreign_staging = _task5a_cache_manifest(foreign_staging)
    fixture = _task5a_lifecycle_fixture()
    source = fixture["source"]
    route = fixture["route"]
    target = cache_root / source["source_id"]
    events = []
    target_visibility = []
    collision_manifest = []
    _task5a_install_real_lifecycle_boundary(
        monkeypatch,
        fixture,
        events=events,
        target=target,
        target_visibility=target_visibility,
    )
    real_loader = source_fetcher.load_verified_source

    def replay_then_create_collision(candidate, **kwargs):
        candidate = Path(candidate)
        events.append("offline-replay-enter")
        target_visible_before_replay = target.exists() or target.is_symlink()
        _task5a_assert_complete_hal_candidate(candidate, fixture)
        verified = real_loader(candidate, **kwargs)
        events.append("offline-replay-complete")
        assert candidate != target
        assert target_visible_before_replay is False
        assert not target.exists() and not target.is_symlink()
        target.mkdir()
        if collision_kind == "nonempty":
            target.joinpath("sentinel").write_bytes(b"CONCURRENT-TARGET")
            target.joinpath("nested").mkdir()
            target.joinpath("nested", "payload").write_bytes(
                b"CONCURRENT-NESTED-PAYLOAD"
            )
        collision_manifest.append(_task5a_cache_manifest(target))
        events.append(f"concurrent-{collision_kind}-target-created")
        return verified

    monkeypatch.setattr(
        source_fetcher,
        "load_verified_source",
        replay_then_create_collision,
    )
    outcome = source_fetcher._fetch_source(
        cache_root,
        source,
        route,
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert outcome["status"] == "failed", outcome
    _task5a_assert_inputs_complete_before(events, "offline-replay-enter")
    _task5a_assert_event_order(
        events,
        "offline-replay-enter",
        "offline-hal-crossref-validator-enter",
        "offline-hal-crossref-validator-complete",
        "offline-replay-complete",
        f"concurrent-{collision_kind}-target-created",
    )
    assert len(collision_manifest) == 1
    assert target.is_dir() and not target.is_symlink()
    assert _task5a_cache_manifest(target) == collision_manifest[0]
    assert not any(visible for _event, visible in target_visibility)
    assert _task5a_cache_manifest(existing) == before_existing
    assert _task5a_cache_manifest(foreign_staging) == before_foreign_staging
    assert {path.name for path in cache_root.iterdir()} == {
        ".foreign-operation-staging",
        "preexisting_source",
        source["source_id"],
    }


TASK5A_GAREL_IDENTITY = {
    "kind": "doi",
    "value": "10.1088/0305-4470/16/10/023",
}
TASK5A_HAL_BASE = "https://api.archives-ouvertes.fr/search/"
TASK5A_HAL_STABLE_ID = "hal-02340631v1"
TASK5A_HAL_STABLE_URL = "https://hal.science/hal-02340631v1"
TASK5A_HAL_FIELD_PROJECTION = (
    "docid,linkExtId_s,linkExtUrl_s,title_s,journalTitle_s,authFullName_s,"
    "halId_s,uri_s,version_i,submitType_s,docType_s,issue_s,page_s,volume_s,"
    "doiId_s,producedDateY_i,publicationDate_s"
)
TASK5A_HAL_QUERY_PAIRS = (
    ("q", "halId_s:hal-02340631 AND version_i:1"),
    ("fl", TASK5A_HAL_FIELD_PROJECTION),
    ("rows", "1"),
    ("start", "0"),
    ("wt", "json"),
)
TASK5A_HAL_QUERY = urlencode(TASK5A_HAL_QUERY_PAIRS)
TASK5A_HAL_REQUEST_URL = TASK5A_HAL_BASE + "?" + TASK5A_HAL_QUERY
TASK5A_GAREL_CROSSREF = {
    "doi": TASK5A_GAREL_IDENTITY["value"],
    "title": "Study of a two-dimensional fully frustrated model",
    "authors": ["T. Garel", "J.-M. Maillard"],
    "venue": "Journal of Physics A: Mathematical and General",
    "volume": "16",
    "issue": "10",
    "pages": "2257-2265",
    "publication_date": "1983-07-11",
}
TASK5A_GAREL_PDF_TEXT = """
Study of a two-dimensional fully frustrated model
T Garel
J M Maillard
J. Phys. A : Math. Gen. 16 (1983) 2257-2265. Printed in Great Britain
The model exhibits the exact target-bearing frustrated phase discussed below.
"""


def test_task5a_hal_query_uses_stdlib_urlencode_on_exact_ordered_pairs():
    assert TASK5A_HAL_QUERY_PAIRS == (
        ("q", "halId_s:hal-02340631 AND version_i:1"),
        ("fl", TASK5A_HAL_FIELD_PROJECTION),
        ("rows", "1"),
        ("start", "0"),
        ("wt", "json"),
    )
    assert TASK5A_HAL_QUERY == urlencode(TASK5A_HAL_QUERY_PAIRS)
    assert TASK5A_HAL_QUERY == (
        "q=halId_s%3Ahal-02340631+AND+version_i%3A1&"
        "fl=docid%2ClinkExtId_s%2ClinkExtUrl_s%2Ctitle_s%2CjournalTitle_s%2C"
        "authFullName_s%2ChalId_s%2Curi_s%2Cversion_i%2CsubmitType_s%2C"
        "docType_s%2Cissue_s%2Cpage_s%2Cvolume_s%2CdoiId_s%2CproducedDateY_i%2C"
        "publicationDate_s&rows=1&start=0&wt=json"
    )


def _task5a_hal_document():
    return {
        "response": {
            "numFound": 1,
            "start": 0,
            "numFoundExact": True,
            "docs": [
                {
                    "docid": "2340631",
                    "linkExtId_s": "istex",
                    "linkExtUrl_s": (
                        "https://api.istex.fr/document/"
                        "315C04C1B2CFE6FA0DE1A3BAA04E06FA586E5893/"
                        "fulltext/pdf?sid=hal"
                    ),
                    "title_s": [
                        "Study of a two-dimensional fully frustrated model"
                    ],
                    "journalTitle_s": (
                        "Journal of Physics A: Mathematical and General "
                        "(1975 - 2006)"
                    ),
                    "authFullName_s": ["T. Garel", "J-M. Maillard"],
                    "halId_s": "hal-02340631",
                    "uri_s": TASK5A_HAL_STABLE_URL,
                    "version_i": 1,
                    "submitType_s": "notice",
                    "docType_s": "ART",
                    "issue_s": ["10"],
                    "page_s": "2257-2265",
                    "volume_s": "16",
                    "doiId_s": TASK5A_GAREL_IDENTITY["value"],
                    "producedDateY_i": 1983,
                    "publicationDate_s": "1983-07-11",
                }
            ],
        }
    }


def _task5a_validate_hal(document, *, crossref=None):
    return validate_work_identity_document(
        document,
        identity=TASK5A_GAREL_IDENTITY,
        authoritative_route=_task5a_garel_route(),
        evidence_kind="hal_same_work_bibliographic_payload",
        bibliographic_metadata=(
            TASK5A_GAREL_CROSSREF if crossref is None else crossref
        ),
    )


def test_task5a_garel_route_pins_query_free_hal_base_stable_id_and_document_url():
    route = _task5a_garel_route()
    assert route == {
        "kind": "author_repository_pdf",
        "url": (
            "https://www.lptmc.jussieu.fr/files/maillard/PUB2/"
            "Frustrated_jav16i10p2257.pdf"
        ),
        "expected_media_type": "application/pdf",
        "access_mode": "unattended",
        "artifact_identifier": "author-repository:Frustrated_jav16i10p2257.pdf",
        "work_identity_evidence": {
            "kind": "hal_same_work_bibliographic_payload",
            "url": TASK5A_HAL_BASE,
            "record_identifier": TASK5A_HAL_STABLE_ID,
            "stable_document_url": TASK5A_HAL_STABLE_URL,
        },
    }


def test_task5a_hal_strict_positive_requires_the_complete_fixed_record():
    _task5a_validate_hal(_task5a_hal_document())


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        ("numFound", "numFound"),
        ("start", "start"),
        ("numFoundExact", "numFoundExact"),
        ("docs-cardinality", "one.*document|docs"),
        ("docid", "docid"),
        ("halId_s", "HAL|halId"),
        ("version_i", "version"),
        ("uri_s", "URI|uri"),
        ("submitType_s", "submitType|notice"),
        ("docType_s", "docType|ART"),
        ("doiId_s", "DOI"),
        ("title_s", "title"),
        ("authFullName_s", "author"),
        ("author-order", "author|order"),
        ("journalTitle_s", "journal|venue"),
        ("volume_s", "volume"),
        ("issue_s", "issue"),
        ("page_s", "page"),
        ("producedDateY_i", "year|date"),
        ("publicationDate_s", "publication|date"),
        ("linkExtId_s", "ISTEX|linkExtId"),
        ("linkExtUrl_s", "ISTEX|linkExtUrl"),
    ),
)
def test_task5a_hal_rejects_each_independently_mutated_fixed_field(
    mutation,
    match,
):
    document = _task5a_hal_document()
    response = document["response"]
    record = response["docs"][0]
    if mutation == "numFound":
        response[mutation] = 2
    elif mutation == "start":
        response[mutation] = 1
    elif mutation == "numFoundExact":
        response[mutation] = False
    elif mutation == "docs-cardinality":
        response["docs"].append(copy.deepcopy(record))
    elif mutation == "author-order":
        record["authFullName_s"].reverse()
    elif mutation in {"version_i", "producedDateY_i"}:
        record[mutation] += 1
    elif mutation == "issue_s":
        record[mutation] = ["11"]
    elif mutation == "title_s":
        record[mutation] = ["A different frustrated model"]
    elif mutation == "authFullName_s":
        record[mutation][1] = "J. Different"
    else:
        record[mutation] = str(record[mutation]) + "-mutated"
    with pytest.raises(SourceEvidenceError, match=match):
        _task5a_validate_hal(document)


def test_task5a_hal_rejects_duplicate_json_key_before_record_validation():
    raw = json.dumps(_task5a_hal_document(), separators=(",", ":")).encode("utf-8")
    raw = raw.replace(
        b'"docid":"2340631"',
        b'"docid":"2340631","docid":"2340631"',
        1,
    )
    with pytest.raises(SourceEvidenceError, match="strict JSON"):
        document = evidence_sources._load_json_bytes(
            raw,
            context="HAL work identity evidence JSON",
        )
        _task5a_validate_hal(document)


@pytest.mark.parametrize(
    ("field", "mutated", "match"),
    (
        ("doi", "10.1088/0305-4470/16/10/999", "DOI"),
        ("title", "A different paper", "title"),
        ("authors", ["J.-M. Maillard", "T. Garel"], "author|order"),
        ("authors", ["T. Garel"], "author|cardinality"),
        ("venue", "Journal of Physics B", "venue|journal"),
        ("volume", "17", "volume"),
        ("issue", "11", "issue"),
        ("pages", "2257-2266", "page"),
        ("publication_date", "1983-07-12", "date"),
    ),
)
def test_task5a_hal_crossref_agreement_rejects_each_field_mutation(
    field,
    mutated,
    match,
):
    crossref = copy.deepcopy(TASK5A_GAREL_CROSSREF)
    crossref[field] = mutated
    with pytest.raises(SourceEvidenceError, match=match):
        _task5a_validate_hal(_task5a_hal_document(), crossref=crossref)


def test_task5a_garel_hal_crossref_and_doi_absent_pdf_agree_transitively():
    evidence_sources._validate_garel_hal_crossref_pdf_agreement(
        _task5a_hal_document(),
        crossref_metadata=TASK5A_GAREL_CROSSREF,
        extracted_pdf_text=TASK5A_GAREL_PDF_TEXT,
        identity=TASK5A_GAREL_IDENTITY,
        authoritative_route=_task5a_garel_route(),
    )


@pytest.mark.parametrize(
    ("old", "new", "match"),
    (
        (
            "Study of a two-dimensional fully frustrated model",
            "Study of a different model",
            "title",
        ),
        ("T Garel", "A Different", "author"),
        ("J M Maillard", "J Different", "author"),
        (
            "J. Phys. A : Math. Gen. 16 (1983) 2257-2265. Printed in Great Britain",
            "J. Phys. A : Math. Gen. 17 (1984) 2257-2265. Printed in Great Britain",
            "header|journal|volume|year",
        ),
    ),
)
def test_task5a_garel_pdf_rejects_each_bibliographic_fingerprint_mutation(
    old,
    new,
    match,
):
    with pytest.raises(SourceEvidenceError, match=match):
        evidence_sources._validate_garel_hal_crossref_pdf_agreement(
            _task5a_hal_document(),
            crossref_metadata=TASK5A_GAREL_CROSSREF,
            extracted_pdf_text=TASK5A_GAREL_PDF_TEXT.replace(old, new),
            identity=TASK5A_GAREL_IDENTITY,
            authoritative_route=_task5a_garel_route(),
        )


@pytest.mark.parametrize("route_mutation", ("different-doi", "different-kind", "different-sidecar"))
def test_task5a_pdf_doi_absence_exception_is_closed_to_exact_garel_hal_route(
    route_mutation,
):
    identity = copy.deepcopy(TASK5A_GAREL_IDENTITY)
    route = copy.deepcopy(_task5a_garel_route())
    if route_mutation == "different-doi":
        identity["value"] = "10.1088/0305-4470/16/10/999"
    elif route_mutation == "different-kind":
        route["kind"] = "institutional_repository_pdf"
    else:
        route["work_identity_evidence"]["kind"] = "core_same_work_output"
    with pytest.raises(SourceEvidenceError, match="DOI|Garel|HAL|route"):
        evidence_sources._validate_garel_hal_crossref_pdf_agreement(
            _task5a_hal_document(),
            crossref_metadata=TASK5A_GAREL_CROSSREF,
            extracted_pdf_text=TASK5A_GAREL_PDF_TEXT,
            identity=identity,
            authoritative_route=route,
        )


def test_task5a_hal_fetch_uses_exact_ordered_query_but_serializes_only_stable_urls(
    monkeypatch,
):
    raw = json.dumps(_task5a_hal_document(), separators=(",", ":")).encode("utf-8")
    requests = []

    class FixtureOpener:
        def open(self, request, timeout):
            requests.append((request.full_url, dict(request.header_items()), timeout))
            return _FixtureHTTPResponse(
                raw,
                content_type="application/json",
                final_url=request.full_url,
            )

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )
    monkeypatch.setattr(
        source_fetcher,
        "validate_work_identity_document",
        lambda *args, **kwargs: None,
    )
    route = {"authoritative_retrieval_route": _task5a_garel_route()}
    evidence = source_fetcher._fetch_work_identity_evidence(
        {"canonical_identity": TASK5A_GAREL_IDENTITY},
        route,
        object(),
        bibliographic_metadata=TASK5A_GAREL_CROSSREF,
    )

    expected_query = urlencode(TASK5A_HAL_QUERY_PAIRS)
    assert expected_query == TASK5A_HAL_QUERY
    assert "fl=docid%2ClinkExtId_s%2ClinkExtUrl_s%2Ctitle_s" in expected_query
    assert requests == [
        (
            TASK5A_HAL_BASE + "?" + expected_query,
            {"Accept": "application/json", "User-agent": source_fetcher.USER_AGENT},
            30,
        )
    ]
    assert evidence["payload"] == raw
    assert evidence["descriptor"] == {
        "kind": "hal_same_work_bibliographic_payload",
        "url": TASK5A_HAL_BASE,
        "document_base_url": TASK5A_HAL_STABLE_URL,
        "media_type": "application/json",
        "payload_relative_path": "work-identity.json",
        "payload_sha256": hashlib.sha256(raw).hexdigest(),
        "payload_byte_length": len(raw),
    }
    serialized = json.dumps(evidence["descriptor"], sort_keys=True)
    assert TASK5A_HAL_QUERY not in serialized
    assert "?" not in serialized


TASK5A_CORE_INITIAL_URL = "https://core.ac.uk/download/572184419.pdf"
TASK5A_CORE_SECOND_URL = (
    "https://fileserver-az.core.ac.uk/download/572184419.pdf"
)
TASK5A_CORE_FINAL_BASE = (
    "https://pdf.core.ac.uk/corefilesystem/pdf/363/572184419.pdf"
)
TASK5A_CORE_SIGNED_QUERY = "download-token=TASK5A_CORE_MEMORY_ONLY_SIGNATURE"


def test_task5a_core_sidecar_requires_exact_raw_authors_and_canonical_tuples():
    document = _core_mg_work_identity_document()
    validate_work_identity_document(
        document,
        identity={"kind": "doi", "value": CORE_MG_BIBLIOGRAPHIC_METADATA["doi"]},
        authoritative_route=_core_mg_route(),
        evidence_kind="core_same_work_output",
        bibliographic_metadata=CORE_MG_BIBLIOGRAPHIC_METADATA,
    )
    assert evidence_sources._ordered_bibliographic_author_tuples(
        [author["name"] for author in document["authors"]],
        source_kind="core",
    ) == [
        ("caspers", "wj"),
        ("emmett", "km"),
        ("magnus", "w"),
    ]


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        ("missing", "author|cardinality"),
        ("extra", "author|cardinality"),
        ("reordered", "author|order"),
        ("duplicate", "author|duplicate|collision"),
        ("ambiguous", "author|ambiguous"),
        ("colliding", "author|collision|duplicate"),
        ("wrong-initial-order", "author|initial"),
    ),
)
def test_task5a_core_rejects_every_ordered_raw_author_tuple_mutation(
    mutation,
    match,
):
    document = _core_mg_work_identity_document()
    authors = document["authors"]
    if mutation == "missing":
        authors.pop()
    elif mutation == "extra":
        authors.append({"name": "Additional, A."})
    elif mutation == "reordered":
        authors[0], authors[1] = authors[1], authors[0]
    elif mutation == "duplicate":
        authors[1] = copy.deepcopy(authors[0])
    elif mutation == "ambiguous":
        authors[0] = {"name": "W.J. Caspers, Jr."}
    elif mutation == "colliding":
        authors[:] = [{"name": "Caspers, W.J."}, {"name": "W J Caspers"}, authors[2]]
    else:
        authors[0] = {"name": "Caspers, J.W."}
    with pytest.raises(SourceEvidenceError, match=match):
        validate_work_identity_document(
            document,
            identity={
                "kind": "doi",
                "value": CORE_MG_BIBLIOGRAPHIC_METADATA["doi"],
            },
            authoritative_route=_core_mg_route(),
            evidence_kind="core_same_work_output",
            bibliographic_metadata=CORE_MG_BIBLIOGRAPHIC_METADATA,
        )


def _task5a_core_redirect_handler():
    return source_fetcher._CoreFullTextRedirectHandler(None)


def _task5a_redirect_request(handler, request, new_url):
    return handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        new_url,
    )


def test_task5a_core_redirects_follow_only_exact_three_hop_sequence_and_two_redirects(
    monkeypatch,
):
    constructed = []

    def construct_after_validation(_handler, request, _fp, _code, _msg, _headers, new_url):
        constructed.append(new_url)
        return Request(new_url, headers=dict(request.header_items()))

    monkeypatch.setattr(
        source_fetcher.HTTPRedirectHandler,
        "redirect_request",
        construct_after_validation,
    )
    handler = _task5a_core_redirect_handler()
    first = Request(TASK5A_CORE_INITIAL_URL)
    second = _task5a_redirect_request(handler, first, TASK5A_CORE_SECOND_URL)
    signed_final = TASK5A_CORE_FINAL_BASE + "?" + TASK5A_CORE_SIGNED_QUERY
    third = _task5a_redirect_request(handler, second, signed_final)

    assert second.full_url == TASK5A_CORE_SECOND_URL
    assert third.full_url == signed_final
    assert constructed == [TASK5A_CORE_SECOND_URL, signed_final]
    with pytest.raises(SourceEvidenceError, match="redirect|two|depth"):
        _task5a_redirect_request(handler, third, signed_final)
    assert constructed == [TASK5A_CORE_SECOND_URL, signed_final]


@pytest.mark.parametrize(
    ("stage", "unsafe_url"),
    (
        ("first", "https://evil.invalid/download/572184419.pdf"),
        ("first", "https://fileserver-az.core.ac.uk/download/572184418.pdf"),
        ("first", "https://user:password@fileserver-az.core.ac.uk/download/572184419.pdf"),
        ("first", TASK5A_CORE_SECOND_URL + "?too-early=TASK5A_SECRET"),
        ("first", TASK5A_CORE_SECOND_URL + "#fragment"),
        ("final", "https://evil.invalid/corefilesystem/pdf/363/572184419.pdf"),
        ("final", "https://pdf.core.ac.uk/corefilesystem/pdf/364/572184419.pdf"),
        ("final", "https://user@pdf.core.ac.uk/corefilesystem/pdf/363/572184419.pdf"),
        ("final", TASK5A_CORE_FINAL_BASE + "#fragment"),
    ),
)
def test_task5a_core_rejects_unsafe_redirect_before_request_construction_or_issue(
    monkeypatch,
    stage,
    unsafe_url,
):
    constructed = []

    def forbidden_super(*args, **kwargs):
        constructed.append((args, kwargs))
        raise AssertionError("unsafe CORE request was constructed")

    monkeypatch.setattr(
        source_fetcher.HTTPRedirectHandler,
        "redirect_request",
        forbidden_super,
    )
    handler = _task5a_core_redirect_handler()
    initial = Request(TASK5A_CORE_INITIAL_URL)
    if stage == "first":
        previous = initial
    else:
        monkeypatch.setattr(
            source_fetcher.HTTPRedirectHandler,
            "redirect_request",
            lambda _handler, request, _fp, _code, _msg, _headers, new_url: Request(
                new_url,
                headers=dict(request.header_items()),
            ),
        )
        previous = _task5a_redirect_request(
            handler,
            initial,
            TASK5A_CORE_SECOND_URL,
        )
        monkeypatch.setattr(
            source_fetcher.HTTPRedirectHandler,
            "redirect_request",
            forbidden_super,
        )
    with pytest.raises(SourceEvidenceError, match="CORE|redirect|userinfo|query|fragment"):
        _task5a_redirect_request(handler, previous, unsafe_url)
    assert constructed == []


def test_task5a_core_redirect_rejects_credential_bearing_request_before_super(
    monkeypatch,
):
    super_calls = []
    monkeypatch.setattr(
        source_fetcher.HTTPRedirectHandler,
        "redirect_request",
        lambda *args, **kwargs: super_calls.append((args, kwargs)),
    )
    request = Request(
        TASK5A_CORE_INITIAL_URL,
        headers={"Authorization": "TASK5A_FORBIDDEN_CORE_CREDENTIAL"},
    )
    with pytest.raises(SourceEvidenceError, match="credential|header"):
        _task5a_redirect_request(
            _task5a_core_redirect_handler(),
            request,
            TASK5A_CORE_SECOND_URL,
        )
    assert super_calls == []


def test_task5a_core_final_signed_query_is_used_in_memory_but_never_serialized(
    monkeypatch,
):
    route = copy.deepcopy(_core_mg_route())
    route["expected_media_type"] = "application/pdf"
    signed_final = TASK5A_CORE_FINAL_BASE + "?" + TASK5A_CORE_SIGNED_QUERY
    requested = []

    class FixtureOpener:
        def open(self, request, timeout):
            requested.append(request.full_url)
            return _FixtureHTTPResponse(
                _minimal_pdf("CORE signed query in-memory control."),
                content_type="application/pdf",
                final_url=signed_final,
            )

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )
    response = source_fetcher._download(route, object())

    assert requested == [TASK5A_CORE_INITIAL_URL]
    assert response["final_url"] == TASK5A_CORE_FINAL_BASE
    assert TASK5A_CORE_SIGNED_QUERY not in json.dumps(response, sort_keys=True)


def test_task5a_core_sidecar_validation_precedes_even_first_pdf_request_construction(
    tmp_path,
    monkeypatch,
):
    source = {
        "source_id": "doi_e49cda761520424da334",
        "canonical_identity": {
            "kind": "doi",
            "value": CORE_MG_BIBLIOGRAPHIC_METADATA["doi"],
        },
        "canonical_url": (
            "https://doi.org/" + CORE_MG_BIBLIOGRAPHIC_METADATA["doi"]
        ),
        "benchmark_names": ["task5a_core_order_fixture"],
    }
    route = {
        "source_id": source["source_id"],
        "authoritative_retrieval_route": _core_mg_route(),
        "expected_media_type": "application/pdf",
        "access_mode": "unattended",
        "local_cache_location": f"source-cache/{source['source_id']}/source.pdf",
    }
    events = []
    monkeypatch.setattr(source_fetcher, "_ssl_context", lambda _path: object())
    monkeypatch.setattr(
        source_fetcher,
        "_fetch_bibliographic_metadata",
        lambda *args, **kwargs: copy.deepcopy(CORE_MG_BIBLIOGRAPHIC_METADATA),
    )

    def validated_sidecar(*args, **kwargs):
        events.append("CORE-sidecar-fetched-hashed-and-validated")
        return {
            "payload": json.dumps(_core_mg_work_identity_document()).encode("utf-8"),
            "descriptor": {"payload_relative_path": "work-identity.json"},
        }

    def construct_first_pdf_request(*args, **kwargs):
        events.append("first-PDF-request-constructed")
        raise SourceEvidenceError("stop after request-construction ordering probe")

    monkeypatch.setattr(
        source_fetcher,
        "_fetch_work_identity_evidence",
        validated_sidecar,
    )
    monkeypatch.setattr(source_fetcher, "_download", construct_first_pdf_request)

    outcome = source_fetcher._fetch_source(
        tmp_path,
        source,
        route,
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert outcome["status"] == "failed"
    assert events == [
        "CORE-sidecar-fetched-hashed-and-validated",
        "first-PDF-request-constructed",
    ]
    assert not (tmp_path / source["source_id"]).exists()


TASK5A_OUP_IDENTITY = {"kind": "doi", "value": "10.1143/ptp/5.2.177"}
TASK5A_OUP_SOURCE_ID = "doi_457c49167653440059e9"
TASK5A_OUP_CROSSREF_URL = (
    "https://api.crossref.org/works/10.1143%2Fptp%2F5.2.177"
)
TASK5A_OUP_PRIMARY_RESOURCE_URL = (
    "https://academic.oup.com/ptp/article-lookup/doi/10.1143/ptp/5.2.177"
)


def _task5a_oup_crossref_document():
    return {
        "status": "ok",
        "message-type": "work",
        "message-version": "1.0.0",
        "message": {
            "DOI": TASK5A_OUP_IDENTITY["value"],
            "title": ["The Statistics of Honeycomb and Triangular Lattice. I"],
            "author": [
                {"given": "Kodi", "family": "Husimi"},
                {"given": "Itiro", "family": "Syozi"},
            ],
            "publisher": "Oxford University Press (OUP)",
            "member": "286",
            "type": "journal-article",
            "volume": "5",
            "issue": "2",
            "page": "177-186",
            "resource": {"primary": {"URL": TASK5A_OUP_PRIMARY_RESOURCE_URL}},
        },
    }


def _task5a_oup_crossref_metadata():
    return {
        "doi": TASK5A_OUP_IDENTITY["value"],
        "title": "The Statistics of Honeycomb and Triangular Lattice. I",
        "authors": ["Kodi Husimi", "Itiro Syozi"],
        "venue": "Progress of Theoretical Physics",
        "publication_date": "1950-03-01",
        "volume": "5",
        "issue": "2",
        "pages": "177-186",
    }


def _task5a_validate_oup_crossref(document):
    return validate_work_identity_document(
        document,
        identity=TASK5A_OUP_IDENTITY,
        authoritative_route=_oup_html_route(),
        evidence_kind="crossref_oup_same_work",
        bibliographic_metadata=_task5a_oup_crossref_metadata(),
    )


def test_task5a_oup_route_uses_slash_identity_new_source_artifact_and_crossref_sidecar(
    tmp_path,
):
    assert _oup_html_route() == {
        "kind": "oup_minimal_html",
        "url": "https://oup.silverchair-cdn.com/article-minimal/1942776",
        "expected_media_type": "text/html",
        "access_mode": "unattended",
        "artifact_identifier": "oup-silverchair-article-minimal:1942776",
        "work_identity_evidence": {
            "kind": "crossref_oup_same_work",
            "url": TASK5A_OUP_CROSSREF_URL,
        },
    }
    source_dir, source, route = _write_oup_html_source(tmp_path)
    assert source_dir.name == TASK5A_OUP_SOURCE_ID
    assert source["source_id"] == route["source_id"] == TASK5A_OUP_SOURCE_ID


def test_task5a_oup_source_id_and_cache_path_are_deterministic(tmp_path):
    source_dir, source, route = _write_oup_html_source(tmp_path)
    assert source_dir == tmp_path / TASK5A_OUP_SOURCE_ID
    assert source["canonical_identity"] == TASK5A_OUP_IDENTITY
    assert source["canonical_url"] == "https://doi.org/10.1143/ptp/5.2.177"
    assert route["local_cache_location"] == (
        "source-cache/doi_457c49167653440059e9/source.html"
    )


def test_task5a_oup_crossref_strict_positive_requires_complete_fixed_work_record():
    _task5a_validate_oup_crossref(_task5a_oup_crossref_document())


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        ("status", "status"),
        ("message-type", "message.?type|work"),
        ("message-shape", "message|response"),
        ("doi", "DOI"),
        ("title", "title"),
        ("author-family", "author|family"),
        ("author-initial", "author|initial"),
        ("author-order", "author|order"),
        ("author-cardinality", "author|cardinality"),
        ("publisher", "publisher"),
        ("member", "member"),
        ("type", "type|journal"),
        ("volume", "volume"),
        ("issue", "issue"),
        ("pages", "page"),
        ("primary-resource", "resource|URL|origin|path"),
    ),
)
def test_task5a_oup_crossref_rejects_each_independent_response_mutation(
    mutation,
    match,
):
    document = _task5a_oup_crossref_document()
    message = document["message"]
    if mutation == "status":
        document["status"] = "failed"
    elif mutation == "message-type":
        document["message-type"] = "member"
    elif mutation == "message-shape":
        document["message"] = [message]
    elif mutation == "doi":
        message["DOI"] = "10.1143/ptp/5.2.178"
    elif mutation == "title":
        message["title"] = ["A different lattice paper"]
    elif mutation == "author-family":
        message["author"][0]["family"] = "Different"
    elif mutation == "author-initial":
        message["author"][0]["given"] = "Taro"
    elif mutation == "author-order":
        message["author"].reverse()
    elif mutation == "author-cardinality":
        message["author"].pop()
    elif mutation == "primary-resource":
        message["resource"]["primary"]["URL"] += "?download=1"
    elif mutation == "pages":
        message["page"] = "177-187"
    else:
        message[mutation] = str(message[mutation]) + "-mutated"
    with pytest.raises(SourceEvidenceError, match=match):
        _task5a_validate_oup_crossref(document)


def test_task5a_oup_crossref_raw_response_is_single_metadata_and_sidecar_source(
    monkeypatch,
):
    raw = json.dumps(
        _task5a_oup_crossref_document(),
        separators=(",", ":"),
    ).encode("utf-8")
    requests = []

    class FixtureOpener:
        def open(self, request, timeout):
            requests.append((request.full_url, timeout))
            return _FixtureHTTPResponse(
                raw,
                content_type="application/json",
                final_url=TASK5A_OUP_CROSSREF_URL,
            )

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )
    bundle = source_fetcher._fetch_crossref_oup_same_work_bundle(
        {"canonical_identity": TASK5A_OUP_IDENTITY},
        {"authoritative_retrieval_route": _oup_html_route()},
        object(),
    )

    assert requests == [(TASK5A_OUP_CROSSREF_URL, 30)]
    assert bundle["raw_payload"] == raw
    assert bundle["bibliographic_metadata"] == _task5a_oup_crossref_metadata()
    assert bundle["identity_evidence"] == {
        "payload": raw,
        "descriptor": {
            "kind": "crossref_oup_same_work",
            "url": TASK5A_OUP_CROSSREF_URL,
            "document_base_url": TASK5A_OUP_CROSSREF_URL,
            "media_type": "application/json",
            "payload_relative_path": "work-identity.json",
            "payload_sha256": hashlib.sha256(raw).hexdigest(),
            "payload_byte_length": len(raw),
        },
    }


def _task5a_oup_dom_mutation(mutation):
    payload = OUP_HTML
    if mutation == "duplicate-container":
        payload = payload.replace(b"</body>", OUP_HTML.split(b"<body>", 1)[1].split(b"</body>", 1)[0] + b"</body>", 1)
    elif mutation == "missing-header":
        payload = payload.replace(b'class="article-header"', b'class="removed-header"', 1)
    elif mutation == "duplicate-header":
        header = payload.split(b'<header class="article-header">', 1)[1].split(b"</header>", 1)[0]
        payload = payload.replace(b"</header>", b"</header><header class=\"article-header\">" + header + b"</header>", 1)
    elif mutation == "content-before-header":
        header_start = payload.index(b'      <header class="article-header">')
        header_end = payload.index(b"</header>", header_start) + len(b"</header>")
        content_start = payload.index(
            b'      <section class="article-content">', header_end
        )
        content_end = payload.index(b"</section>", content_start) + len(
            b"</section>"
        )
        header_subtree = payload[header_start:header_end]
        separator = payload[header_end:content_start]
        content_subtree = payload[content_start:content_end]
        payload = (
            payload[:header_start]
            + content_subtree
            + separator
            + header_subtree
            + payload[content_end:]
        )
        assert header_subtree in payload and content_subtree in payload
        assert payload.index(content_subtree) < payload.index(header_subtree)
    elif mutation == "citation-outside-header":
        payload = payload.replace(b'class="ww-citation-primary"', b'class="removed-citation"', 1).replace(b"</section>", b'<div class="ww-citation-primary">citation</div></section>', 1)
    elif mutation == "citation-inside-content":
        payload = payload.replace(b'class="ww-citation-primary"', b'class="removed-citation"', 1).replace(b'<section class="article-content">', b'<section class="article-content"><div class="ww-citation-primary">citation</div>', 1)
    elif mutation == "duplicate-citation":
        payload = payload.replace(b"</header>", b'<div class="ww-citation-primary">duplicate</div></header>', 1)
    elif mutation == "missing-ref-list":
        payload = payload.replace(b'class="ref-list"', b'class="removed-ref-list"', 1)
    elif mutation == "duplicate-ref-list":
        payload = payload.replace(b"</section>", b'<div class="ref-list">duplicate</div></section>', 1)
    elif mutation == "ref-list-in-header":
        payload = payload.replace(b'class="ref-list"', b'class="removed-ref-list"', 1).replace(b"</header>", b'<div class="ref-list">wrong region</div></header>', 1)
    else:
        raise AssertionError(f"unknown OUP DOM mutation {mutation}")
    assert payload != OUP_HTML
    return payload


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        ("duplicate-container", "container|one"),
        ("missing-header", "header"),
        ("duplicate-header", "header|one"),
        ("content-before-header", "order|header|content"),
        ("citation-outside-header", "citation|header"),
        ("citation-inside-content", "citation|content|header"),
        ("duplicate-citation", "citation|one"),
        ("missing-ref-list", "reference|ref-list"),
        ("duplicate-ref-list", "reference|ref-list|one"),
        ("ref-list-in-header", "reference|ref-list|header|content"),
    ),
)
def test_task5a_oup_rejects_each_dom_hierarchy_and_cardinality_mutation(
    mutation,
    match,
):
    with pytest.raises(SourceEvidenceError, match=match):
        _validate_oup_html_payload(_task5a_oup_dom_mutation(mutation))


@pytest.mark.parametrize(
    ("old", "new", "match"),
    (
        (b"Kodi Husimi", b"Taro Husimi", "author"),
        (b"Itiro Sy&#244;zi", b"Itiro Different", "author"),
        (b"Volume 5", b"Volume 6", "volume"),
        (b"Issue 2", b"Issue 3", "issue"),
        (b"March 1950", b"April 1950", "date|March"),
        (b"Pages 177-186", b"Pages 177-187", "page"),
        (b"Summary", b"Overview", "Summary|summary"),
        (b"ch 2H = 2", b"ch 2H = 3", "equation"),
        (b"exp(4H) = 3", b"exp(4H) = 4", "equation"),
    ),
)
def test_task5a_oup_rejects_each_visible_identity_bibliographic_and_equation_mutation(
    old,
    new,
    match,
):
    payload = OUP_HTML.replace(old, new, 1)
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match=match):
        _validate_oup_html_payload(payload)


def test_task5a_oup_rejects_header_h1_title_mutation_while_head_title_is_unchanged():
    head_title = (
        b"<title>The Statistics of Honeycomb and Triangular Lattice. I</title>"
    )
    header_title = (
        b"<h1>The Statistics of Honeycomb and Triangular Lattice. I</h1>"
    )
    payload = OUP_HTML.replace(header_title, b"<h1>Different title</h1>", 1)
    assert head_title in payload
    assert header_title not in payload
    with pytest.raises(SourceEvidenceError, match="title"):
        _validate_oup_html_payload(payload)


def test_task5a_oup_head_title_is_not_an_article_title_identity_carrier():
    header_title = (
        b"<h1>The Statistics of Honeycomb and Triangular Lattice. I</h1>"
    )
    payload = OUP_HTML.replace(
        b"<title>The Statistics of Honeycomb and Triangular Lattice. I</title>",
        b"<title>Publisher navigation title</title>",
        1,
    )
    assert header_title in payload
    assert _validate_oup_html_payload(payload) == "text/html"


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        ("href", "href|DOI|anchor"),
        ("text", "text|DOI|anchor"),
        ("href-query", "query|DOI|anchor"),
        ("missing", "DOI|anchor"),
    ),
)
def test_task5a_oup_identity_anchor_requires_exact_matching_href_and_visible_text(
    mutation,
    match,
):
    payload = OUP_HTML
    exact_anchor = (
        b'<a href="' + OUP_RESOLVER + b'"><p>' + OUP_RESOLVER + b"</p></a>"
    )
    assert OUP_HTML.count(exact_anchor) == 1
    if mutation == "href":
        mutated_anchor = exact_anchor.replace(
            b'href="' + OUP_RESOLVER + b'"',
            b'href="https://doi.org/10.1143/ptp/5.2.178"',
            1,
        )
    elif mutation == "text":
        mutated_anchor = exact_anchor.replace(
            b"><p>" + OUP_RESOLVER + b"</p>",
            b"><p>10.1143/ptp/5.2.177</p>",
            1,
        )
    elif mutation == "href-query":
        mutated_anchor = exact_anchor.replace(
            b'href="' + OUP_RESOLVER + b'"',
            b'href="' + OUP_RESOLVER + b'?download=1"',
            1,
        )
    else:
        payload = payload.replace(b'class="ww-citation-primary"', b'class="removed-citation"', 1)
        mutated_anchor = None
    if mutated_anchor is not None:
        payload = payload.replace(exact_anchor, mutated_anchor, 1)
        if mutation == "text":
            assert b'href="' + OUP_RESOLVER + b'"' in payload
        else:
            assert b"><p>" + OUP_RESOLVER + b"</p>" in payload
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match=match):
        _validate_oup_html_payload(payload)


@pytest.mark.parametrize("carrier_kind", ("plain", "element", "canonical-anchor"))
def test_task5a_oup_rejects_every_second_identity_carrier_outside_exact_ref_list(
    carrier_kind,
):
    carrier = {
        "plain": OUP_DOI,
        "element": b"<span>" + OUP_DOI + b"</span>",
        "canonical-anchor": b'<a href="' + OUP_RESOLVER + b'">' + OUP_DOI + b"</a>",
    }[carrier_kind]
    payload = OUP_HTML.replace(b"</header>", carrier + b"</header>", 1)
    with pytest.raises(SourceEvidenceError, match="DOI|carrier"):
        _validate_oup_html_payload(payload)


def test_task5a_oup_excludes_only_cited_dois_inside_structurally_exact_ref_list():
    assert _validate_oup_html_payload(OUP_HTML) == "text/html"
    payload = OUP_HTML.replace(
        b'class="ref-list"',
        b'class="lookalike-reference-list"',
        1,
    )
    with pytest.raises(SourceEvidenceError, match="DOI|reference|ref-list"):
        _validate_oup_html_payload(payload)


TASK5A_OUP_LIVE_HIDING_SELECTORS = (
    b".article-header > .task5a-header-hidden",
    b".article-content > .task5a-content-hidden",
    b".minimal-article-container .task5a-container-hidden",
)


def _task5a_oup_css_v2_payload(stylesheet):
    header_hidden = (
        b'<span class="task5a-header-hidden">10.2000/header-extra</span>'
    )
    content_hidden = (
        b'<span class="task5a-content-hidden">10.2000/content-extra</span>'
        b'<div class="task5a-container-hidden"><span>10.2000/nested-extra</span></div>'
    )
    payload = OUP_HTML.replace(b"</header>", header_hidden + b"</header>", 1)
    payload = payload.replace(b"</section>", content_hidden + b"</section>", 1)
    payload = payload.replace(
        b"</head>",
        b"<style>" + stylesheet + b"</style></head>",
        1,
    )
    return payload


def test_task5a_oup_css_v2_matches_three_live_child_and_descendant_selectors_with_ancestor_hiding():
    stylesheet = b"\n".join(
        selector + b" { display:none }"
        for selector in TASK5A_OUP_LIVE_HIDING_SELECTORS
    )
    assert _validate_oup_html_payload(
        _task5a_oup_css_v2_payload(stylesheet)
    ) == "text/html"


@pytest.mark.parametrize(
    "selector",
    (
        b".minimal-article-container .article-header > .task5a-header-hidden",
        b".article-header + .task5a-header-hidden",
        b".article-header ~ .task5a-header-hidden",
        b".article-header[data-kind]",
        b".article-header:first-child",
        b"* > .task5a-header-hidden",
        b"svg|a > .task5a-header-hidden",
        b".article\\2d header > .task5a-header-hidden",
        b".article-header >",
    ),
)
def test_task5a_oup_css_v2_rejects_every_prohibited_hiding_selector_grammar(
    selector,
):
    payload = _task5a_oup_css_v2_payload(selector + b" { display:none }")
    with pytest.raises(SourceEvidenceError, match="CSS|selector|style"):
        _validate_oup_html_payload(payload)


@pytest.mark.parametrize(
    "stylesheet",
    (
        b"@media print { .task5a-header-hidden { display:none } }",
        b"@supports (display:block) { .task5a-header-hidden { display:none } }",
        b'@import url("https://styles.invalid/oup.css");',
        b"@namespace svg url(http://www.w3.org/2000/svg);",
        b"/* unterminated",
        b".task5a-header-hidden { display:none ",
    ),
)
def test_task5a_oup_css_v2_rejects_block_external_other_at_rules_and_malformed_css(
    stylesheet,
):
    with pytest.raises(SourceEvidenceError, match="CSS|style|at-rule|malformed"):
        _validate_oup_html_payload(_task5a_oup_css_v2_payload(stylesheet))


def test_task5a_oup_css_v2_preserves_nonhiding_complex_selectors_and_statement_at_rules():
    stylesheet = (
        b'@charset "UTF-8"; @layer task5a; '
        b".complex > *[data-anything]:first-child { color:red } "
        + b" ".join(
            selector + b" { display:none }"
            for selector in TASK5A_OUP_LIVE_HIDING_SELECTORS
        )
    )
    assert _validate_oup_html_payload(
        _task5a_oup_css_v2_payload(stylesheet)
    ) == "text/html"


def test_task5a_oup_css_v2_rejects_external_stylesheet_without_fetch(monkeypatch):
    monkeypatch.setattr(
        source_fetcher,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("external CSS fetch attempted")
        ),
    )
    payload = OUP_HTML.replace(
        b"</head>",
        b'<link rel="stylesheet" href="https://styles.invalid/oup.css"></head>',
        1,
    )
    with pytest.raises(SourceEvidenceError, match="style|external|CSS"):
        _validate_oup_html_payload(payload)


@pytest.mark.parametrize("limit_kind", ("characters", "rules"))
def test_task5a_oup_css_v2_enforces_stylesheet_limits(
    monkeypatch,
    limit_kind,
):
    if limit_kind == "characters":
        monkeypatch.setattr(evidence_sources, "_MAX_LOCAL_STYLESHEET_CHARACTERS", 8)
    else:
        monkeypatch.setattr(evidence_sources, "_MAX_LOCAL_STYLESHEET_RULES", 1)
    stylesheet = b" ".join(
        selector + b" { display:none }"
        for selector in TASK5A_OUP_LIVE_HIDING_SELECTORS
    )
    with pytest.raises(SourceEvidenceError, match="too many|too large|limit|CSS"):
        _validate_oup_html_payload(_task5a_oup_css_v2_payload(stylesheet))


def _task5a_html_extraction_provenance(source, route, response):
    return source_fetcher._build_provenance(
        source,
        route,
        response,
        _task5a_oup_crossref_metadata(),
        payload_name="source.html",
    )


def _task5a_corrected_html_extraction_inputs():
    source = {
        "source_id": TASK5A_OUP_SOURCE_ID,
        "canonical_identity": copy.deepcopy(TASK5A_OUP_IDENTITY),
        "canonical_url": "https://doi.org/10.1143/ptp/5.2.177",
    }
    route = {"authoritative_retrieval_route": copy.deepcopy(_oup_html_route())}
    response = {
        "body": OUP_HTML,
        "status": 200,
        "headers": {"Content-Type": "text/html"},
        "final_url": _oup_html_route()["url"],
        "media_type": "text/html",
    }
    return source, route, response


def test_task5a_html_extraction_descriptor_v2_is_exact_corrected_route(monkeypatch):
    monkeypatch.setattr(source_fetcher, "_pdftotext_version", lambda: "unused")
    source, route, response = _task5a_corrected_html_extraction_inputs()
    corrected = _task5a_html_extraction_provenance(source, route, response)
    assert corrected["text_extraction"] == {
        "tool": "stdlib_html_visible_text",
        "version": 2,
        "deterministic": True,
        "arguments": [],
    }


@pytest.mark.parametrize(
    "scope_mutation",
    (
        "canonical-doi",
        "route-kind",
        "artifact-identifier",
        "primary-route-url",
        "source-id",
    ),
)
def test_task5a_html_extraction_descriptor_v2_rejects_each_single_scope_mutation(
    monkeypatch,
    scope_mutation,
):
    monkeypatch.setattr(source_fetcher, "_pdftotext_version", lambda: "unused")
    source, route, response = _task5a_corrected_html_extraction_inputs()
    if scope_mutation == "canonical-doi":
        source["canonical_identity"]["value"] = "10.1143/ptp/5.2.178"
    elif scope_mutation == "route-kind":
        route["authoritative_retrieval_route"]["kind"] = "author_repository_pdf"
    elif scope_mutation == "artifact-identifier":
        route["authoritative_retrieval_route"]["artifact_identifier"] = (
            "oup-silverchair-article-minimal:1942777"
        )
    elif scope_mutation == "primary-route-url":
        route["authoritative_retrieval_route"]["url"] = (
            "https://oup.silverchair-cdn.com/article-minimal/1942777"
        )
    else:
        source["source_id"] = "doi_other_html_route"
    other = _task5a_html_extraction_provenance(source, route, response)
    assert other["text_extraction"] == {
        "tool": "stdlib_html_visible_text",
        "version": 1,
        "deterministic": True,
        "arguments": [],
    }


TASK5A_GENERIC_V1_DOI = b"10.1143/ptp.5.2.177"
TASK5A_GENERIC_V1_RESOLVER = b"https://doi.org/" + TASK5A_GENERIC_V1_DOI
TASK5A_GENERIC_V1_SOURCE_ID = "doi_task5a_generic_v1_html"


def _task5a_generic_v1_html_payload():
    exact_anchor = (
        b'<a href="' + OUP_RESOLVER + b'"><p>' + OUP_RESOLVER + b"</p></a>"
    )
    assert OUP_HTML.count(exact_anchor) == 1
    payload = OUP_HTML.replace(
        exact_anchor,
        b"<p>" + TASK5A_GENERIC_V1_RESOLVER + b"</p>",
        1,
    )
    return payload.replace(
        b'<a href="https://doi.org/10.1000/cited-work">10.1000/cited-work</a>',
        b"legacy reference without a DOI carrier",
        1,
    )


def _task5a_generic_v1_html_contract(payload):
    route_spec = {
        "kind": "oup_minimal_html",
        "url": "https://oup.silverchair-cdn.com/article-minimal/generic-v1-control",
        "expected_media_type": "text/html",
        "access_mode": "unattended",
        "artifact_identifier": "oup-silverchair-article-minimal:generic-v1-control",
        "work_identity_evidence": {
            "kind": "canonical_identity",
            "url": "https://doi.org/10.1143/ptp.5.2.177",
        },
    }
    source = {
        "source_id": TASK5A_GENERIC_V1_SOURCE_ID,
        "canonical_identity": {
            "kind": "doi",
            "value": TASK5A_GENERIC_V1_DOI.decode("ascii"),
        },
        "canonical_url": TASK5A_GENERIC_V1_RESOLVER.decode("ascii"),
    }
    route = {
        "source_id": source["source_id"],
        "authoritative_retrieval_route": route_spec,
        "expected_media_type": "text/html",
        "access_mode": "unattended",
        "local_cache_location": (
            f"source-cache/{source['source_id']}/source.html"
        ),
    }
    response = {
        "body": payload,
        "status": 200,
        "headers": {"Content-Type": "text/html"},
        "final_url": route_spec["url"],
        "media_type": "text/html",
    }
    bibliographic = {
        "title": "The Statistics of Honeycomb and Triangular Lattice. I",
        "authors": ["Kodi Husimi", "Itiro Syozi"],
        "venue": "Progress of Theoretical Physics",
        "publication_date": "1950-03-01",
    }
    provenance = source_fetcher._build_provenance(
        source,
        route,
        response,
        bibliographic,
        payload_name="source.html",
    )
    assert provenance["text_extraction"] == {
        "tool": "stdlib_html_visible_text",
        "version": 1,
        "deterministic": True,
        "arguments": [],
    }
    return source, route, response, provenance


def _task5a_validate_generic_v1_html(payload, validation_mode, tmp_path):
    source, route, response, provenance = _task5a_generic_v1_html_contract(payload)
    if validation_mode == "download":
        return validate_download_response(
            route["authoritative_retrieval_route"],
            status=response["status"],
            headers=response["headers"],
            body=response["body"],
            final_url=response["final_url"],
        )
    assert validation_mode == "offline"
    source_dir = tmp_path / source["source_id"]
    source_dir.mkdir()
    source_dir.joinpath("source.html").write_bytes(payload)
    source_dir.joinpath("provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verified = load_verified_source(
        source_dir,
        expected_source=source,
        provisioning_route=route,
    )
    assert verified.extraction_tool["version"] == 1
    return verified


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    "meta_name",
    (b"citation_doi", b"dc.identifier.doi", b"prism.doi"),
)
def test_task5a_generic_v1_html_preserves_sole_head_metadata_identity(
    tmp_path,
    validation_mode,
    meta_name,
):
    payload = _task5a_generic_v1_html_payload().replace(
        b"<p>" + TASK5A_GENERIC_V1_RESOLVER + b"</p>",
        b"",
        1,
    )
    payload = _oup_html_with_head_meta(
        payload,
        meta_name,
        TASK5A_GENERIC_V1_DOI.upper(),
    )
    _task5a_validate_generic_v1_html(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
@pytest.mark.parametrize(
    "presentation",
    (
        TASK5A_GENERIC_V1_DOI,
        b"DOI: " + TASK5A_GENERIC_V1_DOI + b".",
        b"DOI: " + TASK5A_GENERIC_V1_DOI + b", verified",
        b"(DOI: " + TASK5A_GENERIC_V1_DOI + b")",
        b"(DOI: " + TASK5A_GENERIC_V1_DOI + b").",
        b"(" + TASK5A_GENERIC_V1_RESOLVER + b").",
        b"See (" + TASK5A_GENERIC_V1_DOI + b").",
        TASK5A_GENERIC_V1_DOI + b".",
        TASK5A_GENERIC_V1_DOI + b", verified",
        TASK5A_GENERIC_V1_RESOLVER + b".",
        TASK5A_GENERIC_V1_RESOLVER + b", verified",
    ),
)
def test_task5a_generic_v1_html_preserves_legal_doi_presentation_normalization(
    tmp_path,
    validation_mode,
    presentation,
):
    payload = _task5a_generic_v1_html_payload().replace(
        TASK5A_GENERIC_V1_RESOLVER,
        presentation,
        1,
    )
    _task5a_validate_generic_v1_html(payload, validation_mode, tmp_path)
