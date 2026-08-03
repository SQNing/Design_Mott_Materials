import builtins
from collections import Counter
import copy
import ctypes
import errno
import hashlib
import io
import json
import os
import random
import re
import signal
import socket
import struct
import subprocess
import sys
import time
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
    source_id_for_identity,
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
        <p class="authors">Kodi Husimi and Itiro Sy&#244;zi</p>
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
    lines = text.splitlines() or [""]
    escaped_lines = [
        line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        for line in lines
    ]
    operations = ["BT /F1 12 Tf 72 720 Td"]
    for index, escaped in enumerate(escaped_lines):
        if index:
            operations.append("0 -18 Td")
        operations.append(f"({escaped}) Tj")
    operations.append("ET")
    stream = " ".join(operations).encode("ascii")
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
CORE_MG_PDF_TEXT = "\n".join(
    (
        "The Majumdar-Ghosh chain. Twofold ground state and elementary excitations",
        "W J Caspers, K M Emmett and W Magnus",
        "Abstract",
    )
)


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
    payload = _minimal_pdf(
        CORE_MG_PDF_TEXT
        if evidence_kind == "core_same_work_output"
        else "Locally verified special-route source payload."
    )
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
    canonical_url = "https://doi.org/10.1143/ptp/5.2.177"
    identity_string = canonical_source_identity(canonical_url)
    identity_kind, identity_value = identity_string.split(":", 1)
    source_id = source_id_for_identity(identity_string)
    route_spec = _oup_html_route()
    source = {
        "source_id": source_id,
        "canonical_identity": {
            "kind": identity_kind,
            "value": identity_value,
        },
        "canonical_url": canonical_url,
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
    identity_fixture = _task5a_oup_acquisition_fixture()
    assert identity_fixture["source"] == source
    assert identity_fixture["route"] == route
    provenance = _provenance(payload)
    provenance.update(
        {
            "source_id": source_id,
            "source_identity": {
                **source["canonical_identity"],
                "canonical_url": source["canonical_url"],
            },
            "bibliographic_metadata": {
                key: copy.deepcopy(identity_fixture["bibliographic"][key])
                for key in (
                    "title",
                    "authors",
                    "venue",
                    "publication_date",
                )
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
            "work_identity_evidence": copy.deepcopy(
                route_spec["work_identity_evidence"]
            ),
        }
    )
    source_dir = tmp_path / source_id
    source_dir.mkdir()
    source_dir.joinpath("source.html").write_bytes(payload)
    source_dir.joinpath("provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    source_dir.joinpath("work-identity.json").write_bytes(
        identity_fixture["crossref_raw"]
    )
    source_dir.joinpath("work-identity.provenance.json").write_text(
        json.dumps(
            identity_fixture["sidecar_descriptor"],
            indent=2,
            sort_keys=True,
        )
        + "\n",
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
            b"<p>" + OUP_RESOLVER + b"</p>",
            b'<p style="' + style + b'">' + OUP_RESOLVER + b"</p>",
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
            b"<p>" + OUP_RESOLVER + b"</p>",
            b'<p class="hide-doi">' + OUP_RESOLVER + b"</p>",
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
        b"<p>" + OUP_RESOLVER + b"</p>",
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
        b"<p>" + OUP_RESOLVER + b"</p>",
        b'<p style="' + style + b'">' + OUP_RESOLVER + b"</p>",
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
def test_structured_doi_oup_rejects_inline_style_hidden_extra_doi(
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
    with pytest.raises(SourceEvidenceError, match="DOI|carrier|ref-list"):
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
        b"<p>" + OUP_RESOLVER + b"</p>",
        doi_markup + OUP_RESOLVER + closing_tag,
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
def test_structured_doi_oup_rejects_stylesheet_hidden_extra_doi(
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
    with pytest.raises(SourceEvidenceError, match="DOI|carrier|ref-list"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
def test_structured_doi_oup_ordinary_stylesheet_class_remains_visible(
    tmp_path,
    validation_mode,
):
    payload = OUP_HTML.replace(
        b"<p>" + OUP_RESOLVER + b"</p>",
        b'<p class="show-doi">' + OUP_RESOLVER + b"</p>",
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
def test_round7_b_oup_v2_accepts_one_descendant_hiding_selector(
    tmp_path,
    validation_mode,
    extra_doi,
):
    payload = _oup_payload_with_local_stylesheet(
        b"article .hide-doi { display:none }",
        extra_doi=extra_doi,
    )

    with pytest.raises(SourceEvidenceError, match="DOI|anchor|carrier"):
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

    with pytest.raises(SourceEvidenceError, match="DOI|carrier"):
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
    sidecar_reads, _real_io_open = _task5a_install_snapshot_read_recorder(
        monkeypatch,
        tmp_path,
    )

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

    assert outcome["status"] == "acquired"
    assert len(sidecar_reads) == 1
    operation, replay_path, _mode, _flags = sidecar_reads[0]
    assert operation in {"io.open", "builtins.open", "os.open"}
    assert replay_path.name == sidecar_path.name
    assert replay_path.parent.parent == tmp_path
    assert replay_path.parent.name.startswith(".literature-evidence-staging-")
    assert replay_path != sidecar_path
    assert sidecar_path.is_file()


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


TASK5A_IN_CREATE = 0x00000100
TASK5A_IN_DELETE = 0x00000200
TASK5A_IN_MOVED_FROM = 0x00000040
TASK5A_IN_MOVED_TO = 0x00000080
TASK5A_IN_ISDIR = 0x40000000
TASK5A_INOTIFY_EVENT = struct.Struct("iIII")


def _task5a_parse_inotify_payload(payload):
    events = []
    offset = 0
    while offset < len(payload):
        assert offset + TASK5A_INOTIFY_EVENT.size <= len(payload)
        wd, mask, cookie, name_length = TASK5A_INOTIFY_EVENT.unpack_from(
            payload,
            offset,
        )
        offset += TASK5A_INOTIFY_EVENT.size
        name_end = offset + name_length
        assert name_end <= len(payload)
        name_bytes = bytes(payload[offset:name_end]).split(b"\0", 1)[0]
        offset = name_end
        events.append(
            {
                "wd": wd,
                "mask": mask,
                "cookie": cookie,
                "name": os.fsdecode(name_bytes),
            }
        )
    assert offset == len(payload)
    return events


def _task5a_observer_teardown_cause(*errors):
    retained_errors = []
    for error in errors:
        if error is None or any(
            error is retained_error
            for retained_error in retained_errors
        ):
            continue
        retained_errors.append(error)
    if len(retained_errors) == 1:
        return retained_errors[0]
    aggregate_error = AssertionError("multiple observer teardown failures")
    aggregate_error.observer_teardown_errors = tuple(retained_errors)
    return aggregate_error


class _Task5AInotifyWatch:
    def __init__(self, root):
        self.root = Path(root)
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.inotify_init1.argtypes = [ctypes.c_int]
        self.libc.inotify_init1.restype = ctypes.c_int
        self.libc.inotify_add_watch.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint32,
        ]
        self.libc.inotify_add_watch.restype = ctypes.c_int
        self.libc.inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
        self.libc.inotify_rm_watch.restype = ctypes.c_int
        self.fd = self.libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
        mask = (
            TASK5A_IN_CREATE
            | TASK5A_IN_DELETE
            | TASK5A_IN_MOVED_FROM
            | TASK5A_IN_MOVED_TO
        )
        self.wd = self.libc.inotify_add_watch(
            self.fd,
            os.fsencode(self.root),
            mask,
        )
        if self.wd < 0:
            error = ctypes.get_errno()
            os.close(self.fd)
            self.fd = -1
            raise OSError(error, os.strerror(error), self.root)

    def read_events(self):
        payload = bytearray()
        while True:
            try:
                chunk = os.read(self.fd, 64 * 1024)
            except BlockingIOError:
                break
            if not chunk:
                break
            payload.extend(chunk)
        return _task5a_parse_inotify_payload(payload)

    def finish(self):
        try:
            events = self.read_events()
        except BaseException as read_error:
            existing_read_cause = read_error.__cause__
            existing_read_context = read_error.__context__
            try:
                self.close()
            except BaseException as close_error:
                raise read_error from _task5a_observer_teardown_cause(
                    existing_read_cause,
                    close_error,
                    existing_read_context,
                )
            raise
        self.close()
        return {"backend": "inotify", "events": events}

    def close(self):
        if self.fd < 0:
            return
        result = self.libc.inotify_rm_watch(self.fd, self.wd)
        if result < 0:
            error = ctypes.get_errno()
            if error != errno.EINVAL:
                os.close(self.fd)
                self.fd = -1
                raise OSError(error, os.strerror(error), self.root)
        os.close(self.fd)
        self.fd = -1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


def _task5a_unwatched_inotify_finish_control(root):
    watch = _Task5AInotifyWatch.__new__(_Task5AInotifyWatch)
    watch.root = Path(root)
    watch.libc = ctypes.CDLL(None, use_errno=True)
    watch.libc.inotify_init1.argtypes = [ctypes.c_int]
    watch.libc.inotify_init1.restype = ctypes.c_int
    watch.libc.inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
    watch.libc.inotify_rm_watch.restype = ctypes.c_int
    watch.fd = watch.libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
    if watch.fd < 0:
        error = ctypes.get_errno()
        if error in {errno.ENOSPC, errno.EMFILE, errno.ENFILE}:
            pytest.skip("inotify finish control unavailable")
        raise OSError(error, os.strerror(error))
    watch.wd = -1
    return watch


TASK5A_STRACE_OPERATIONS = (
    "rename",
    "renameat",
    "renameat2",
    "mkdir",
    "mkdirat",
    "mknod",
    "mknodat",
    "open",
    "openat",
    "creat",
    "unlink",
    "unlinkat",
    "rmdir",
    "symlink",
    "symlinkat",
    "link",
    "linkat",
    "truncate",
    "ftruncate",
    "fallocate",
    "write",
    "writev",
    "pwrite64",
    "pwritev",
    "chmod",
    "fchmod",
    "fchmodat",
    "chown",
    "fchown",
    "lchown",
    "fchownat",
    "utime",
    "utimes",
    "utimensat",
    "setxattr",
    "lsetxattr",
    "fsetxattr",
    "removexattr",
    "lremovexattr",
    "fremovexattr",
)
TASK5A_STRACE_SYSCALLS = ",".join(TASK5A_STRACE_OPERATIONS)
TASK5A_STRACE_CALL = re.compile(
    r"^(?:(?:\[pid\s+\d+\]|\d+)\s+)?"
    rf"(?P<operation>{'|'.join(TASK5A_STRACE_OPERATIONS)})"
    r"\((?P<arguments>.*)\)\s+=\s+(?P<result>-?\d+)"
    r"(?:<[^>]*>)?(?:\s|$)"
)
TASK5A_STRACE_QUOTED_PATH = re.compile(r'"(?:\\.|[^"\\])*"')
TASK5A_STRACE_DIRFD = re.compile(
    r"^(?P<descriptor>AT_FDCWD|-?\d+)(?:<(?P<path>.*)>)?$"
)
TASK5A_STRACE_FD = re.compile(r"^-?\d+<(?P<path>.*)>$")
TASK5A_STRACE_OPEN_MUTATION = re.compile(
    r"\b(?:O_WRONLY|O_RDWR|O_CREAT|O_TRUNC|O_APPEND|O_TMPFILE)\b"
)
TASK5A_STRACE_FD_MUTATIONS = {
    "ftruncate",
    "fallocate",
    "write",
    "writev",
    "pwrite64",
    "pwritev",
    "fchmod",
    "fchown",
    "fsetxattr",
    "fremovexattr",
}
TASK5A_STRACE_EARLY_DEATH = (
    "strace observer died before controlled teardown"
)
TASK5A_STRACE_INCOMPLETE = (
    "strace observer did not record a completed teardown checkpoint"
)
TASK5A_STRACE_CHECKPOINT_PREFIX = ".task5a-strace-checkpoint-"


def _task5a_split_strace_arguments(arguments):
    tokens = []
    start = 0
    quote = False
    escaped = False
    stack = []
    closing = {"<": ">", "(": ")", "[": "]", "{": "}"}
    for offset, character in enumerate(arguments):
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quote = False
            continue
        if character == '"':
            quote = True
        elif character in closing:
            stack.append(closing[character])
        elif stack and character == stack[-1]:
            stack.pop()
        elif character == "," and not stack:
            tokens.append(arguments[start:offset].strip())
            start = offset + 1
    assert not quote and not escaped and not stack, arguments
    tokens.append(arguments[start:].strip())
    return tuple(tokens)


def _task5a_strace_dirfd_base(token, *, cwd):
    match = TASK5A_STRACE_DIRFD.fullmatch(token)
    assert match is not None, token
    annotated_path = match.group("path")
    if annotated_path is not None:
        return Path(os.path.abspath(annotated_path))
    assert match.group("descriptor") == "AT_FDCWD", (
        "numeric strace dirfd lacks the path annotation requested by -yy: "
        + token
    )
    return cwd


def _task5a_resolve_strace_path(token, *, cwd, dirfd=None):
    assert TASK5A_STRACE_QUOTED_PATH.fullmatch(token), token
    path = Path(json.loads(token))
    if not path.is_absolute():
        base = cwd if dirfd is None else _task5a_strace_dirfd_base(dirfd, cwd=cwd)
        path = base / path
    return Path(os.path.abspath(path))


def _task5a_resolve_strace_fd_path(token):
    match = TASK5A_STRACE_FD.fullmatch(token)
    assert match is not None, (
        "strace file descriptor lacks the path annotation requested by -yy"
    )
    annotated_path = match.group("path")
    if annotated_path.endswith(" (deleted)"):
        annotated_path = annotated_path[: -len(" (deleted)")]
    return Path(os.path.abspath(annotated_path))


def _task5a_strace_operation_paths(operation, tokens, *, cwd):
    if operation in {"rename", "link"}:
        assert len(tokens) >= 2, tokens
        return (
            _task5a_resolve_strace_path(tokens[0], cwd=cwd),
            _task5a_resolve_strace_path(tokens[1], cwd=cwd),
        )
    if operation in {"renameat", "renameat2", "linkat"}:
        assert len(tokens) >= 4, tokens
        return (
            _task5a_resolve_strace_path(tokens[1], cwd=cwd, dirfd=tokens[0]),
            _task5a_resolve_strace_path(tokens[3], cwd=cwd, dirfd=tokens[2]),
        )
    if operation in {
        "mkdirat",
        "mknodat",
        "openat",
        "unlinkat",
        "fchmodat",
        "fchownat",
        "utimensat",
    }:
        assert len(tokens) >= 2, tokens
        return (
            _task5a_resolve_strace_path(tokens[1], cwd=cwd, dirfd=tokens[0]),
        )
    if operation == "symlinkat":
        assert len(tokens) >= 3, tokens
        return (
            _task5a_resolve_strace_path(tokens[2], cwd=cwd, dirfd=tokens[1]),
        )
    if operation == "symlink":
        assert len(tokens) >= 2, tokens
        return (_task5a_resolve_strace_path(tokens[1], cwd=cwd),)
    if operation in TASK5A_STRACE_FD_MUTATIONS:
        assert tokens, tokens
        return (_task5a_resolve_strace_fd_path(tokens[0]),)
    assert tokens, tokens
    assert TASK5A_STRACE_QUOTED_PATH.fullmatch(tokens[0]), tokens
    return (_task5a_resolve_strace_path(tokens[0], cwd=cwd),)


def _task5a_parse_strace_payload(payload, *, cwd=None):
    cwd = Path(os.path.abspath(Path.cwd() if cwd is None else cwd))
    records = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        match = TASK5A_STRACE_CALL.match(line.strip())
        if match is None:
            continue
        arguments = match.group("arguments")
        argument_tokens = _task5a_split_strace_arguments(arguments)
        paths = _task5a_strace_operation_paths(
            match.group("operation"),
            argument_tokens,
            cwd=cwd,
        )
        result = int(match.group("result"))
        records.append(
            {
                "line_number": line_number,
                "operation": match.group("operation"),
                "arguments": arguments,
                "argument_tokens": argument_tokens,
                "paths": paths,
                "result": result,
                "success": result >= 0,
                "line": line,
            }
        )
    return records


def _task5a_tracer_pid():
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("TracerPid:"):
            return int(line.split(":", 1)[1].strip())
    raise AssertionError("/proc/self/status omitted TracerPid")


def _task5a_strace_cleanup_error(cleanup_errors):
    if not cleanup_errors:
        return None
    error = AssertionError("strace observer cleanup failed")
    error.cleanup_errors = tuple(cleanup_errors)
    error.__cause__ = cleanup_errors[0]
    error.__suppress_context__ = True
    return error


class _Task5AStraceWatch:
    def __init__(self, root, trace_path):
        self.root = Path(root)
        self.trace_path = Path(trace_path)
        self.process = subprocess.Popen(
            [
                "/usr/bin/strace",
                "-qq",
                "-f",
                "-yy",
                "-s",
                "4096",
                "-e",
                f"trace={TASK5A_STRACE_SYSCALLS}",
                "-p",
                str(os.getpid()),
                "-o",
                str(self.trace_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._shutdown_complete = False
        self._shutdown_state = None
        self._shutdown_error = None
        try:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if _task5a_tracer_pid() == self.process.pid:
                    break
                return_code = self.process.poll()
                if return_code is not None:
                    raise OSError(
                        errno.EPERM,
                        f"strace attach failed ({return_code})",
                    )
                time.sleep(0.01)
            else:
                raise OSError(
                    errno.ETIMEDOUT,
                    "strace did not attach before timeout",
                )
        except BaseException as setup_error:
            _shutdown_state, cleanup_error = self._shutdown_process(
                attempt_controlled_sigint=True
            )
            if cleanup_error is not None:
                raise setup_error from cleanup_error
            raise

    def _shutdown_process(self, *, attempt_controlled_sigint):
        if self._shutdown_complete:
            return self._shutdown_state, self._shutdown_error

        cleanup_errors = []
        state = {
            "alive_before_shutdown": None,
            "communicate_timed_out": False,
            "detached": False,
            "forced_kill": False,
            "returncode": None,
            "sent_controlled_sigint": False,
        }

        def record_cleanup_error(error):
            cleanup_errors.append(error)

        def process_is_alive():
            try:
                return self.process.poll() is None
            except BaseException as error:
                record_cleanup_error(error)
                return None

        def force_kill_if_alive():
            if process_is_alive() is False:
                return
            try:
                self.process.kill()
            except ProcessLookupError:
                return
            except BaseException as error:
                record_cleanup_error(error)
            else:
                state["forced_kill"] = True

        state["alive_before_shutdown"] = process_is_alive()
        signal_failed = False
        if (
            attempt_controlled_sigint
            and state["alive_before_shutdown"] is not False
        ):
            try:
                self.process.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass
            except BaseException as error:
                record_cleanup_error(error)
                signal_failed = True
            else:
                state["sent_controlled_sigint"] = True
        if signal_failed:
            force_kill_if_alive()

        communicate_failed = False
        try:
            self.process.communicate(timeout=5)
        except subprocess.TimeoutExpired as error:
            state["communicate_timed_out"] = True
            record_cleanup_error(error)
            communicate_failed = True
        except BaseException as error:
            record_cleanup_error(error)
            communicate_failed = True
        if communicate_failed:
            force_kill_if_alive()
            try:
                self.process.communicate(timeout=5)
            except BaseException as error:
                record_cleanup_error(error)

        if process_is_alive() is not False:
            force_kill_if_alive()
            try:
                self.process.communicate(timeout=5)
            except BaseException as error:
                record_cleanup_error(error)

        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired as error:
            record_cleanup_error(error)
            force_kill_if_alive()
            try:
                self.process.wait(timeout=5)
            except BaseException as wait_error:
                record_cleanup_error(wait_error)
        except BaseException as error:
            record_cleanup_error(error)

        try:
            state["returncode"] = self.process.returncode
        except BaseException as error:
            record_cleanup_error(error)

        try:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if _task5a_tracer_pid() == 0:
                    state["detached"] = True
                    break
                time.sleep(0.01)
            if not state["detached"]:
                record_cleanup_error(
                    AssertionError("strace failed to detach from pytest")
                )
        except BaseException as error:
            record_cleanup_error(error)

        self._shutdown_state = state
        self._shutdown_error = _task5a_strace_cleanup_error(cleanup_errors)
        self._shutdown_complete = True
        return self._shutdown_state, self._shutdown_error

    def _await_completed_checkpoint(self):
        checkpoint_path = Path(os.path.abspath(self.root)) / (
            f"{TASK5A_STRACE_CHECKPOINT_PREFIX}{self.process.pid}-"
            f"{time.monotonic_ns()}"
        )
        try:
            descriptor = os.open(
                checkpoint_path,
                os.O_RDONLY | os.O_CLOEXEC,
            )
        except FileNotFoundError:
            pass
        except OSError:
            return False
        else:
            os.close(descriptor)
        encoded_path = json.dumps(os.fspath(checkpoint_path))
        deadline = time.monotonic() + 5.0
        while self.process.poll() is None and time.monotonic() < deadline:
            if self.trace_path.is_file():
                try:
                    payload = self.trace_path.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    return False
                for line in payload.splitlines():
                    match = TASK5A_STRACE_CALL.match(line.strip())
                    if (
                        match is not None
                        and match.group("operation") in {"open", "openat"}
                        and encoded_path in match.group("arguments")
                        and "ENOSYS" not in line
                    ):
                        return True
            time.sleep(0.01)
        return False

    def finish(self):
        try:
            alive_at_teardown_start = self.process.poll() is None
            attached_at_teardown_start = (
                _task5a_tracer_pid() == self.process.pid
            )
            checkpoint_complete = False
            if alive_at_teardown_start and attached_at_teardown_start:
                checkpoint_complete = self._await_completed_checkpoint()
            alive_before_controlled_sigint = self.process.poll() is None
            attached_before_controlled_sigint = (
                _task5a_tracer_pid() == self.process.pid
            )
        except BaseException as observation_error:
            _shutdown_state, cleanup_error = self._shutdown_process(
                attempt_controlled_sigint=True
            )
            if cleanup_error is not None:
                raise observation_error from cleanup_error
            raise

        shutdown_state, cleanup_error = self._shutdown_process(
            attempt_controlled_sigint=True
        )
        observation_error = None
        if (
            not alive_at_teardown_start
            or not attached_at_teardown_start
            or not alive_before_controlled_sigint
            or not attached_before_controlled_sigint
            or not shutdown_state["sent_controlled_sigint"]
        ):
            observation_error = AssertionError(TASK5A_STRACE_EARLY_DEATH)
        elif shutdown_state["communicate_timed_out"]:
            observation_error = AssertionError(
                "strace observer did not stop after controlled SIGINT"
            )
        elif shutdown_state["returncode"] != 0:
            observation_error = AssertionError(
                "strace observer returned an unexpected controlled-SIGINT status"
            )
        elif not checkpoint_complete:
            observation_error = AssertionError(TASK5A_STRACE_INCOMPLETE)
        if observation_error is not None:
            if cleanup_error is not None:
                raise observation_error from cleanup_error
            raise observation_error
        if cleanup_error is not None:
            raise cleanup_error
        assert self.trace_path.is_file(), "strace observer did not write its trace"
        payload = self.trace_path.read_text(encoding="utf-8")
        return {
            "backend": "strace",
            "records": _task5a_parse_strace_payload(payload),
            "payload": payload,
        }


def _task5a_required_success_strace_observer(root, trace_path):
    if sys.platform != "linux":
        pytest.skip("Linux renameat2 syscall proof is not portable")
    if not Path("/usr/bin/strace").is_file():
        pytest.fail("required Linux syscall publication proof is unavailable")
    try:
        return _Task5AStraceWatch(root, trace_path)
    except (OSError, subprocess.SubprocessError):
        pytest.fail("required Linux syscall publication proof is unavailable")


def _task5a_optional_inotify_observer(root):
    try:
        return _Task5AInotifyWatch(root)
    except OSError as error:
        if error.errno not in {errno.ENOSPC, errno.EMFILE, errno.ENFILE}:
            raise
        return None


def _task5a_finish_strace_then_optional_inotify(
    strace_observer,
    inotify_observer,
):
    inotify_observation = None
    try:
        strace_observation = strace_observer.finish()
    except BaseException as strace_error:
        existing_strace_cause = strace_error.__cause__
        existing_strace_context = strace_error.__context__
        if inotify_observer is not None:
            try:
                inotify_observer.finish()
            except BaseException as inotify_error:
                raise strace_error from _task5a_observer_teardown_cause(
                    existing_strace_cause,
                    inotify_error,
                    existing_strace_context,
                )
        raise
    if inotify_observer is not None:
        inotify_observation = inotify_observer.finish()
    return strace_observation, inotify_observation


def _task5a_assert_observer_teardown_failures_reachable(error, expected):
    aggregate_error = error.__cause__
    retained_errors = getattr(
        aggregate_error,
        "observer_teardown_errors",
        None,
    )
    assert isinstance(retained_errors, tuple)
    assert len(retained_errors) == len(expected)
    retained_descriptions = {
        (type(retained_error).__name__, str(retained_error))
        for retained_error in retained_errors
    }
    assert retained_descriptions == set(expected)

    reachable_descriptions = set()
    pending = [error]
    seen = set()
    while pending:
        current = pending.pop()
        if not isinstance(current, BaseException) or id(current) in seen:
            continue
        seen.add(id(current))
        reachable_descriptions.add((type(current).__name__, str(current)))
        pending.extend((current.__cause__, current.__context__))
        pending.extend(
            getattr(current, "observer_teardown_errors", ())
        )
    assert set(expected) <= reachable_descriptions


def _task5a_publication_observer_or_skip(root, trace_path):
    if sys.platform != "linux":
        pytest.skip("atomic publication observer requires Linux")
    try:
        return _Task5AInotifyWatch(root)
    except OSError as exc:
        if exc.errno not in {errno.ENOSPC, errno.EMFILE, errno.ENFILE}:
            raise
        inotify_error = exc
    try:
        return _Task5AStraceWatch(root, trace_path)
    except (OSError, subprocess.SubprocessError) as strace_error:
        pytest.skip(
            "atomic publication observer unavailable: "
            f"inotify errno {inotify_error.errno}; strace: {strace_error}"
        )


def _task5a_assert_single_directory_publication(events, target_name):
    target_events = [event for event in events if event["name"] == target_name]
    assert not any(
        event["mask"] & TASK5A_IN_CREATE for event in target_events
    ), target_events
    moved_to = [
        event
        for event in target_events
        if event["mask"] & TASK5A_IN_MOVED_TO
        and event["mask"] & TASK5A_IN_ISDIR
    ]
    assert len(moved_to) == 1, target_events
    cookie = moved_to[0]["cookie"]
    assert cookie != 0
    moved_from = [
        event
        for event in events
        if event["cookie"] == cookie
        and event["mask"] & TASK5A_IN_MOVED_FROM
        and event["mask"] & TASK5A_IN_ISDIR
    ]
    assert len(moved_from) == 1, events
    staging_name = moved_from[0]["name"]
    assert staging_name.startswith(".")
    assert staging_name != target_name
    return staging_name, cookie


def _task5a_strace_rename_paths(record):
    operation = record["operation"]
    if operation == "rename":
        assert len(record["paths"]) == 2, record
        return record["paths"]
    if operation in {"renameat", "renameat2"}:
        assert len(record["paths"]) == 2, record
        return record["paths"]
    raise AssertionError(record)


def _task5a_strace_mutated_paths(record):
    if record["operation"] in {"open", "openat"}:
        if TASK5A_STRACE_OPEN_MUTATION.search(record["arguments"]) is None:
            return ()
    return record["paths"]


def _task5a_path_is_target_or_descendant(path, target):
    return path == target or target in path.parents


def _task5a_assert_strace_single_directory_publication(records, cache_root, target):
    cache_root = Path(os.path.abspath(cache_root))
    target = Path(os.path.abspath(target))
    moves_to_target = []
    for record in records:
        if record["operation"] not in {"rename", "renameat", "renameat2"}:
            continue
        source_path, destination_path = _task5a_strace_rename_paths(record)
        if destination_path == target:
            moves_to_target.append((record, source_path))
    assert len(moves_to_target) == 1, moves_to_target
    publication, staging = moves_to_target[0]
    assert publication["success"], publication
    assert staging.parent == cache_root, publication
    assert staging.name.startswith("."), publication
    assert staging != target, publication
    assert publication["operation"] == "renameat2", (
        "successful publication did not use renameat2"
    )
    assert len(publication["argument_tokens"]) == 5, (
        "renameat2 publication has an unexpected argument shape"
    )
    assert publication["argument_tokens"][4] == "RENAME_NOREPLACE", (
        "renameat2 publication did not use exactly RENAME_NOREPLACE"
    )

    publication_line = publication["line_number"]
    for record in records:
        if record is publication or not record["success"]:
            continue
        for mutated_path in _task5a_strace_mutated_paths(record):
            assert not _task5a_path_is_target_or_descendant(
                mutated_path,
                target,
            ), "successful target mutation occurred outside atomic publication"
    return staging.name, publication_line


def _task5a_assert_successful_publication(observation, cache_root, target):
    assert observation["backend"] == "strace", (
        "successful publication requires syscall-level proof"
    )
    return _task5a_assert_strace_single_directory_publication(
        observation["records"],
        cache_root,
        target,
    )


def _task5a_assert_failed_collision_publication(
    observation,
    cache_root,
    target,
    *,
    candidate,
    foreign_staging,
):
    cache_root = Path(os.path.abspath(cache_root))
    target = Path(os.path.abspath(target))
    candidate = Path(os.path.abspath(candidate))
    foreign_staging = Path(os.path.abspath(foreign_staging))
    assert candidate.parent == cache_root
    assert candidate.name.startswith(".")
    assert candidate not in {target, foreign_staging}
    if observation["backend"] == "inotify":
        target_moves = [
            event
            for event in observation["events"]
            if event["name"] == target.name
            and event["mask"] & TASK5A_IN_MOVED_TO
        ]
        assert target_moves == [], target_moves
        candidate_creates = [
            event
            for event in observation["events"]
            if event["name"] == candidate.name
            and event["mask"] & TASK5A_IN_CREATE
            and event["mask"] & TASK5A_IN_ISDIR
        ]
        assert len(candidate_creates) == 1, observation["events"]
    else:
        assert observation["backend"] == "strace", observation
        moves_to_target = []
        for record in observation["records"]:
            if record["operation"] not in {"rename", "renameat", "renameat2"}:
                continue
            staging, destination = _task5a_strace_rename_paths(record)
            if destination == target:
                moves_to_target.append((record, staging))
        assert not any(record["success"] for record, _path in moves_to_target), (
            moves_to_target
        )
    assert not os.path.lexists(candidate)
    return candidate.name


def _task5a_resolve_open_path(path, *, dir_fd=None):
    resolved = Path(os.fsdecode(path))
    if dir_fd is not None and not resolved.is_absolute():
        resolved = Path(os.readlink(f"/proc/self/fd/{dir_fd}")) / resolved
    return Path(os.path.abspath(resolved))


def _task5a_install_exclusive_write_fault(
    monkeypatch,
    *,
    cache_root,
    basename,
    error_number,
    event_name,
    events,
):
    cache_root = Path(os.path.abspath(cache_root))
    real_io_open = io.open
    real_builtin_open = builtins.open
    real_os_open = os.open
    faults = []

    def inject(operation, path, *, mode=None, flags=None, dir_fd=None):
        resolved = _task5a_resolve_open_path(path, dir_fd=dir_fd)
        try:
            relative = resolved.relative_to(cache_root)
        except ValueError:
            return
        if (
            len(relative.parts) == 2
            and relative.parts[0].startswith(".")
            and relative.parts[1] == basename
        ):
            faults.append(
                {
                    "operation": operation,
                    "path": resolved,
                    "mode": mode,
                    "flags": flags,
                    "errno": error_number,
                }
            )
            events.append(event_name)
            raise OSError(error_number, os.strerror(error_number), resolved)

    def faulting_io_open(path, mode="r", *args, **kwargs):
        if "x" in mode:
            inject("io.open", path, mode=mode)
        return real_io_open(path, mode, *args, **kwargs)

    def faulting_builtin_open(path, mode="r", *args, **kwargs):
        if "x" in mode:
            inject("builtins.open", path, mode=mode)
        return real_builtin_open(path, mode, *args, **kwargs)

    def faulting_os_open(path, flags, mode=0o777, *, dir_fd=None):
        exclusive_create = (
            flags & os.O_CREAT == os.O_CREAT
            and flags & os.O_EXCL == os.O_EXCL
        )
        if exclusive_create:
            inject("os.open", path, flags=flags, dir_fd=dir_fd)
        return real_os_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(io, "open", faulting_io_open)
    monkeypatch.setattr(builtins, "open", faulting_builtin_open)
    monkeypatch.setattr(os, "open", faulting_os_open)
    return faults


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


def _task5a_assert_inputs_complete(events):
    prerequisites = (
        "primary-response-bytes",
        "primary-response-media-validated",
        "crossref-bibliographic-metadata",
        "hal-raw-sidecar-response-bytes",
        "live-hal-crossref-validator-enter",
        "live-hal-crossref-validator-complete",
    )
    assert all(events.count(event) == 1 for event in prerequisites), events
    _task5a_assert_event_order(
        events,
        "hal-raw-sidecar-response-bytes",
        "live-hal-crossref-validator-enter",
        "live-hal-crossref-validator-complete",
    )


def _task5a_assert_inputs_complete_before(events, terminal_event):
    _task5a_assert_inputs_complete(events)
    assert events.count(terminal_event) == 1, events
    terminal_position = events.index(terminal_event)
    prerequisites = (
        "primary-response-media-validated",
        "crossref-bibliographic-metadata",
        "live-hal-crossref-validator-complete",
    )
    assert all(events.index(event) < terminal_position for event in prerequisites), events


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux inotify")
def test_task5a_inotify_event_parser_preserves_masks_names_and_move_cookie():
    cookie = 0x5A51

    def encode(mask, name):
        encoded_name = name.encode("utf-8") + b"\0"
        encoded_name += b"\0" * (-len(encoded_name) % 4)
        return TASK5A_INOTIFY_EVENT.pack(
            7,
            mask,
            cookie,
            len(encoded_name),
        ) + encoded_name

    payload = b"".join(
        (
            encode(
                TASK5A_IN_MOVED_FROM | TASK5A_IN_ISDIR,
                ".invocation-owned-staging",
            ),
            encode(
                TASK5A_IN_MOVED_TO | TASK5A_IN_ISDIR,
                "doi_dba239926d673e54f80a",
            ),
        )
    )
    events = _task5a_parse_inotify_payload(payload)

    staging_name, parsed_cookie = _task5a_assert_single_directory_publication(
        events,
        "doi_dba239926d673e54f80a",
    )
    assert staging_name == ".invocation-owned-staging"
    assert parsed_cookie == cookie


def _task5a_install_raw_inotify_init_failure(monkeypatch, error_number):
    class FailingCFunction:
        def __init__(self, return_value):
            self.return_value = return_value
            self.argtypes = None
            self.restype = None

        def __call__(self, *_args):
            return self.return_value

    class FailingInotifyLibc:
        def __init__(self):
            self.inotify_init1 = FailingCFunction(-1)
            self.inotify_rm_watch = FailingCFunction(-1)

    monkeypatch.setattr(
        ctypes,
        "CDLL",
        lambda *_args, **_kwargs: FailingInotifyLibc(),
    )
    monkeypatch.setattr(ctypes, "get_errno", lambda: error_number)


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux inotify")
@pytest.mark.parametrize(
    "error_number",
    (errno.ENOSPC, errno.EMFILE, errno.ENFILE),
)
def test_task5a_unwatched_inotify_control_skips_optional_resource_exhaustion(
    tmp_path,
    monkeypatch,
    error_number,
):
    _task5a_install_raw_inotify_init_failure(monkeypatch, error_number)

    with pytest.raises(pytest.skip.Exception) as exception_info:
        _task5a_unwatched_inotify_finish_control(tmp_path)

    assert str(exception_info.value) == "inotify finish control unavailable"


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux inotify")
def test_task5a_unwatched_inotify_control_rejects_unexpected_init_errno(
    tmp_path,
    monkeypatch,
):
    _task5a_install_raw_inotify_init_failure(monkeypatch, errno.EIO)

    with pytest.raises(OSError) as exception_info:
        _task5a_unwatched_inotify_finish_control(tmp_path)

    assert exception_info.value.errno == errno.EIO


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux inotify")
def test_task5a_inotify_finish_preserves_read_error_when_close_also_fails(
    tmp_path,
    monkeypatch,
):
    watch_root = tmp_path / "inotify-read-close-failure"
    watch_root.mkdir()
    watch = _task5a_unwatched_inotify_finish_control(watch_root)
    original_fd = watch.fd
    real_close = watch.close

    def failing_read_events():
        raise RuntimeError("inotify read control")

    def close_then_fail():
        real_close()
        raise OSError(errno.EIO, "inotify close control")

    monkeypatch.setattr(watch, "read_events", failing_read_events)
    monkeypatch.setattr(watch, "close", close_then_fail)
    try:
        with pytest.raises(
            RuntimeError,
            match=r"\Ainotify read control\Z",
        ) as exception_info:
            watch.finish()
        assert isinstance(exception_info.value.__cause__, OSError)
        assert exception_info.value.__cause__.errno == errno.EIO
        assert not hasattr(
            exception_info.value.__cause__,
            "observer_teardown_errors",
        )
        assert watch.fd == -1
        with pytest.raises(OSError) as fd_error:
            os.fstat(original_fd)
        assert fd_error.value.errno == errno.EBADF
    finally:
        if watch.fd >= 0:
            real_close()


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux inotify")
def test_task5a_inotify_finish_preserves_precaused_read_body_and_close_failures(
    tmp_path,
    monkeypatch,
):
    watch_root = tmp_path / "inotify-aggregate-failure"
    watch_root.mkdir()
    watch = _task5a_unwatched_inotify_finish_control(watch_root)
    original_fd = watch.fd
    real_close = watch.close

    def failing_read_events():
        raise RuntimeError(
            "precaused inotify read control"
        ) from ValueError("preexisting inotify read cause control")

    def close_then_fail():
        real_close()
        raise OSError(errno.EIO, "inotify aggregate close control")

    monkeypatch.setattr(watch, "read_events", failing_read_events)
    monkeypatch.setattr(watch, "close", close_then_fail)
    try:
        with pytest.raises(
            RuntimeError,
            match=r"\Aprecaused inotify read control\Z",
        ) as exception_info:
            try:
                raise LookupError("inotify body control")
            finally:
                watch.finish()
        _task5a_assert_observer_teardown_failures_reachable(
            exception_info.value,
            {
                (
                    "ValueError",
                    "preexisting inotify read cause control",
                ),
                (
                    "OSError",
                    f"[Errno {errno.EIO}] inotify aggregate close control",
                ),
                ("LookupError", "inotify body control"),
            },
        )
        assert watch.fd == -1
        with pytest.raises(OSError) as fd_error:
            os.fstat(original_fd)
        assert fd_error.value.errno == errno.EBADF
    finally:
        if watch.fd >= 0:
            real_close()


@pytest.mark.parametrize(
    "path_form",
    ("absolute", "numeric-dirfd-relative"),
)
def test_task5a_strace_oracle_accepts_only_noreplace_publication_path_forms(
    path_form,
):
    cache_root = Path("/tmp/task5a-parser-control/source-cache")
    staging = cache_root / ".task5a-observer-control"
    target = cache_root / "published-control"
    if path_form == "absolute":
        open_call = (
            f'417 openat(AT_FDCWD, "{staging}/source.pdf", '
            "O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC, 0666) = 9"
        )
        publication_call = (
            f'417 renameat2(AT_FDCWD, "{staging}", AT_FDCWD, '
            f'"{target}", RENAME_NOREPLACE) = 0'
        )
    else:
        candidate_fd = f"73<{staging}>"
        cache_fd = f"42<{cache_root}>"
        open_call = (
            f'417 openat({candidate_fd}, "source.pdf", '
            f'O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC, 0666) = 9<{staging}/source.pdf>'
        )
        publication_call = (
            f'417 renameat2({cache_fd}, "{staging.name}", {cache_fd}, '
            f'"{target.name}", RENAME_NOREPLACE) = 0'
        )
    payload = "\n".join(
        (
            open_call,
            publication_call,
        )
    )
    records = _task5a_parse_strace_payload(payload)

    staging_name, publication_line = (
        _task5a_assert_strace_single_directory_publication(
            records,
            cache_root,
            target,
        )
    )
    assert [record["operation"] for record in records] == [
        "openat",
        "renameat2",
    ]
    assert records[0]["paths"] == (staging / "source.pdf",)
    assert records[1]["paths"] == (staging, target)
    assert staging_name == staging.name
    assert publication_line == 2


def test_task5a_strace_parser_resolves_numeric_dirfd_renameat_but_oracle_rejects_it():
    cache_root = Path("/tmp/task5a-parser-control/source-cache")
    staging = cache_root / ".task5a-observer-control"
    target = cache_root / "published-control"
    cache_fd = f"42<{cache_root}>"
    records = _task5a_parse_strace_payload(
        f'417 renameat({cache_fd}, "{staging.name}", {cache_fd}, '
        f'"{target.name}") = 0'
    )

    assert records[0]["operation"] == "renameat"
    assert records[0]["paths"] == (staging, target)
    with pytest.raises(AssertionError, match="did not use renameat2"):
        _task5a_assert_strace_single_directory_publication(
            records,
            cache_root,
            target,
        )


@pytest.mark.parametrize(
    "publication_kind",
    ("plain-rename", "renameat", "renameat2-without-flag", "renameat2-extra-flag"),
)
def test_task5a_strace_oracle_rejects_non_noreplace_publication_primitives(
    publication_kind,
):
    cache_root = Path("/tmp/task5a-parser-control/source-cache")
    staging = cache_root / ".task5a-observer-control"
    target = cache_root / "published-control"
    cache_fd = f"42<{cache_root}>"
    publication_calls = {
        "plain-rename": f'417 rename("{staging}", "{target}") = 0',
        "renameat": (
            f'417 renameat({cache_fd}, "{staging.name}", {cache_fd}, '
            f'"{target.name}") = 0'
        ),
        "renameat2-without-flag": (
            f'417 renameat2({cache_fd}, "{staging.name}", {cache_fd}, '
            f'"{target.name}", 0) = 0'
        ),
        "renameat2-extra-flag": (
            f'417 renameat2({cache_fd}, "{staging.name}", {cache_fd}, '
            f'"{target.name}", RENAME_NOREPLACE|RENAME_EXCHANGE) = 0'
        ),
    }
    records = _task5a_parse_strace_payload(publication_calls[publication_kind])

    with pytest.raises(AssertionError):
        _task5a_assert_strace_single_directory_publication(
            records,
            cache_root,
            target,
        )


@pytest.mark.parametrize(
    "mutation_kind",
    ("link", "symlink", "unlink", "rmdir", "truncate-open", "chmod"),
)
@pytest.mark.parametrize("mutation_timing", ("before", "after"))
def test_task5a_strace_oracle_rejects_each_successful_target_mutation_outside_publication(
    mutation_kind,
    mutation_timing,
):
    cache_root = Path("/tmp/task5a-parser-control/source-cache")
    staging = cache_root / ".task5a-observer-control"
    target = cache_root / "published-control"
    target_child = target / "descendant"
    mutation_calls = {
        "link": f'417 link("/tmp/source-control", "{target_child}") = 0',
        "symlink": f'417 symlink("source-control", "{target_child}") = 0',
        "unlink": f'417 unlink("{target_child}") = 0',
        "rmdir": f'417 rmdir("{target_child}") = 0',
        "truncate-open": (
            f'417 openat(AT_FDCWD, "{target_child}", '
            f'O_WRONLY|O_TRUNC|O_CLOEXEC) = 9<{target_child}>'
        ),
        "chmod": f'417 chmod("{target_child}", 0600) = 0',
    }
    publication_call = (
        f'417 renameat2(AT_FDCWD, "{staging}", AT_FDCWD, '
        f'"{target}", RENAME_NOREPLACE) = 0'
    )
    ordered_calls = (
        (mutation_calls[mutation_kind], publication_call)
        if mutation_timing == "before"
        else (publication_call, mutation_calls[mutation_kind])
    )
    payload = "\n".join(ordered_calls)

    with pytest.raises(
        AssertionError,
        match="successful target mutation occurred outside atomic publication",
    ):
        _task5a_assert_strace_single_directory_publication(
            _task5a_parse_strace_payload(payload),
            cache_root,
            target,
        )


@pytest.mark.parametrize("failed_attempts", (0, 2))
def test_task5a_strace_collision_control_accepts_zero_or_more_failed_target_moves(
    tmp_path,
    failed_attempts,
):
    cache_root = tmp_path / "source-cache"
    cache_root.mkdir()
    candidate = cache_root / ".replay-observed-candidate"
    foreign_staging = cache_root / ".foreign-operation-staging"
    foreign_staging.mkdir()
    foreign_staging.joinpath("sentinel").write_bytes(b"FOREIGN-STAGING")
    target = cache_root / "concurrent-target"
    target.write_bytes(b"FOREIGN-TARGET")
    before_foreign = _task5a_cache_manifest(foreign_staging)
    before_target = _round7_tree_snapshot(target)
    cache_fd = f"42<{cache_root}>"
    payload = "\n".join(
        f'417 renameat2({cache_fd}, "{candidate.name}", {cache_fd}, '
        f'"{target.name}", RENAME_NOREPLACE) = -1 EEXIST (File exists)'
        for _attempt in range(failed_attempts)
    )
    observation = {
        "backend": "strace",
        "records": _task5a_parse_strace_payload(payload),
    }

    staging_name = _task5a_assert_failed_collision_publication(
        observation,
        cache_root,
        target,
        candidate=candidate,
        foreign_staging=foreign_staging,
    )

    assert staging_name == candidate.name
    assert not os.path.lexists(candidate)
    assert _task5a_cache_manifest(foreign_staging) == before_foreign
    assert _round7_tree_snapshot(target) == before_target


def test_task5a_strace_collision_control_rejects_successful_target_move(tmp_path):
    cache_root = tmp_path / "source-cache"
    cache_root.mkdir()
    candidate = cache_root / ".replay-observed-candidate"
    foreign_staging = cache_root / ".foreign-operation-staging"
    foreign_staging.mkdir()
    target = cache_root / "concurrent-target"
    target.write_bytes(b"FOREIGN-TARGET")
    cache_fd = f"42<{cache_root}>"
    records = _task5a_parse_strace_payload(
        f'417 renameat2({cache_fd}, "{candidate.name}", {cache_fd}, '
        f'"{target.name}", RENAME_NOREPLACE) = 0'
    )

    with pytest.raises(AssertionError):
        _task5a_assert_failed_collision_publication(
            {"backend": "strace", "records": records},
            cache_root,
            target,
            candidate=candidate,
            foreign_staging=foreign_staging,
        )


def _task5a_run_fork_isolated_control(control):
    read_fd, write_fd = os.pipe()
    child_pid = os.fork()
    if child_pid == 0:
        os.close(read_fd)
        child_exit_code = 0
        try:
            child_result = control()
        except BaseException as error:
            child_result = {
                "harness_error": str(error),
                "harness_error_type": type(error).__name__,
            }
            child_exit_code = 1
        encoded_result = json.dumps(child_result, sort_keys=True).encode("utf-8")
        try:
            os.write(write_fd, encoded_result)
        finally:
            os.close(write_fd)
        os._exit(child_exit_code)

    os.close(write_fd)
    child_payload = bytearray()
    try:
        while True:
            chunk = os.read(read_fd, 4096)
            if not chunk:
                break
            child_payload.extend(chunk)
    finally:
        os.close(read_fd)
    waited_pid, child_status = os.waitpid(child_pid, 0)
    assert waited_pid == child_pid
    assert os.WIFEXITED(child_status)
    assert os.WEXITSTATUS(child_status) == 0, child_payload
    return json.loads(child_payload)


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux observer")
def test_task5a_constructor_communicate_timeout_reaps_and_detaches(tmp_path):
    def constructor_timeout_control():
        real_popen = subprocess.Popen
        real_tracer_pid = _task5a_tracer_pid
        captured_processes = []
        tracer_pid_calls = 0

        class CommunicateTimeoutProcess:
            def __init__(self, *args, **kwargs):
                self.process = real_popen(*args, **kwargs)
                self.communicate_calls = 0
                self.controlled_sigint_calls = 0
                self.kill_calls = 0
                captured_processes.append(self)

            def __getattr__(self, name):
                return getattr(self.process, name)

            def send_signal(self, signal_number):
                if signal_number == signal.SIGINT:
                    self.controlled_sigint_calls += 1
                    return None
                return self.process.send_signal(signal_number)

            def communicate(self, *args, **kwargs):
                self.communicate_calls += 1
                if self.communicate_calls == 1:
                    timeout = kwargs.get("timeout")
                    if timeout is None and args:
                        timeout = args[0]
                    raise subprocess.TimeoutExpired("strace-control", timeout)
                return self.process.communicate(*args, **kwargs)

            def kill(self):
                self.kill_calls += 1
                return self.process.kill()

        def fail_first_tracer_pid_read():
            nonlocal tracer_pid_calls
            tracer_pid_calls += 1
            if tracer_pid_calls == 1:
                raise RuntimeError("constructor state control")
            return real_tracer_pid()

        subprocess.Popen = CommunicateTimeoutProcess
        globals()["_task5a_tracer_pid"] = fail_first_tracer_pid_read
        try:
            try:
                _Task5AStraceWatch(
                    tmp_path,
                    tmp_path / "constructor-timeout.strace",
                )
            except BaseException as error:
                process = captured_processes[0]
                cause = error.__cause__
                result = {
                    "cause": type(cause).__name__ if cause is not None else None,
                    "cleanup_error_types": [
                        type(cleanup_error).__name__
                        for cleanup_error in getattr(cause, "cleanup_errors", ())
                    ],
                    "communicate_calls": process.communicate_calls,
                    "controlled_sigint_calls": process.controlled_sigint_calls,
                    "error": str(error),
                    "error_type": type(error).__name__,
                    "kill_calls": process.kill_calls,
                    "reaped": process.poll() is not None,
                    "tracer_pid": real_tracer_pid(),
                }
            else:
                result = {"unexpected": "constructor failure was accepted"}
        finally:
            globals()["_task5a_tracer_pid"] = real_tracer_pid
            subprocess.Popen = real_popen
            for process in captured_processes:
                if process.process.poll() is None:
                    process.process.kill()
                process.process.communicate(timeout=5)
            deadline = time.monotonic() + 5.0
            while real_tracer_pid() != 0 and time.monotonic() < deadline:
                time.sleep(0.01)
        return result

    result = _task5a_run_fork_isolated_control(constructor_timeout_control)
    assert result["error_type"] == "RuntimeError"
    assert result["error"] == "constructor state control"
    assert result["cause"] == "AssertionError"
    assert "TimeoutExpired" in result["cleanup_error_types"]
    assert result["controlled_sigint_calls"] == 1
    assert result["communicate_calls"] >= 2
    assert result["kill_calls"] >= 1
    assert result["reaped"] is True
    assert result["tracer_pid"] == 0
    assert _task5a_tracer_pid() == 0


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux observer")
def test_task5a_finish_proc_read_failure_reaps_and_detaches(tmp_path):
    def finish_proc_failure_control():
        real_tracer_pid = _task5a_tracer_pid
        cache_root = tmp_path / "finish-proc-failure-source-cache"
        cache_root.mkdir()
        observer = _task5a_required_success_strace_observer(
            cache_root,
            tmp_path / "finish-proc-failure.strace",
        )
        tracer_pid_calls = 0

        def fail_first_tracer_pid_read():
            nonlocal tracer_pid_calls
            tracer_pid_calls += 1
            if tracer_pid_calls == 1:
                raise RuntimeError("finish proc read control")
            return real_tracer_pid()

        globals()["_task5a_tracer_pid"] = fail_first_tracer_pid_read
        try:
            try:
                observer.finish()
            except BaseException as error:
                result = {
                    "cause": (
                        type(error.__cause__).__name__
                        if error.__cause__ is not None
                        else None
                    ),
                    "error": str(error),
                    "error_type": type(error).__name__,
                    "reaped": observer.process.poll() is not None,
                    "tracer_pid": real_tracer_pid(),
                }
            else:
                result = {"unexpected": "finish proc failure was accepted"}
        finally:
            globals()["_task5a_tracer_pid"] = real_tracer_pid
            if observer.process.poll() is None:
                observer.process.kill()
            observer.process.communicate(timeout=5)
            deadline = time.monotonic() + 5.0
            while real_tracer_pid() != 0 and time.monotonic() < deadline:
                time.sleep(0.01)
        return result

    result = _task5a_run_fork_isolated_control(finish_proc_failure_control)
    assert result == {
        "cause": None,
        "error": "finish proc read control",
        "error_type": "RuntimeError",
        "reaped": True,
        "tracer_pid": 0,
    }
    assert _task5a_tracer_pid() == 0


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux observer")
def test_task5a_strace_process_shutdown_is_idempotent_after_finish(
    tmp_path,
    monkeypatch,
):
    cache_root = tmp_path / "idempotent-shutdown-source-cache"
    cache_root.mkdir()
    observer = _task5a_required_success_strace_observer(
        cache_root,
        tmp_path / "idempotent-shutdown.strace",
    )
    observer.finish()

    extra_process_calls = []

    def forbidden_process_call(*_args, **_kwargs):
        extra_process_calls.append("called")
        raise AssertionError("idempotent shutdown repeated a process operation")

    for method_name in ("poll", "send_signal", "communicate", "kill", "wait"):
        monkeypatch.setattr(
            observer.process,
            method_name,
            forbidden_process_call,
        )
    first_state, first_error = observer._shutdown_process(
        attempt_controlled_sigint=True
    )
    second_state, second_error = observer._shutdown_process(
        attempt_controlled_sigint=True
    )

    assert first_state == second_state
    assert first_error is second_error is None
    assert first_state["returncode"] == 0
    assert first_state["detached"] is True
    assert extra_process_calls == []
    assert _task5a_tracer_pid() == 0


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux observer")
@pytest.mark.parametrize(
    "failure_stage",
    (
        "optional-observer-acquisition",
        "directory-fd-acquisition",
        "strace-finish",
        "both-finishes",
        "precaused-body-and-inotify",
        "inotify-read-failure",
    ),
)
def test_task5a_live_noreplace_teardown_reaps_strace_then_closes_optional_observer(
    tmp_path,
    monkeypatch,
    failure_stage,
):
    events = []
    opened_directory_fds = []
    closed_directory_fds = []
    real_inotify_controls = []

    class RequiredStraceControl:
        def finish(self):
            events.append("strace-finish")
            if failure_stage == "precaused-body-and-inotify":
                raise AssertionError(
                    "strace finish control"
                ) from RuntimeError("preexisting strace cause control")
            if failure_stage in {"strace-finish", "both-finishes"}:
                raise AssertionError("strace finish control")
            return {"backend": "strace", "records": [], "payload": ""}

    class OptionalInotifyControl:
        def finish(self):
            events.append("inotify-finish")
            if failure_stage in {
                "both-finishes",
                "precaused-body-and-inotify",
            }:
                raise AssertionError("inotify finish control")
            return {"backend": "inotify", "events": []}

    def required_strace_control(_root, _trace_path):
        events.append("strace-acquired")
        return RequiredStraceControl()

    def optional_inotify_control(_root):
        events.append("inotify-acquisition")
        if failure_stage == "optional-observer-acquisition":
            raise OSError(errno.EIO, "optional observer acquisition control")
        if failure_stage == "inotify-read-failure":
            watch = _task5a_unwatched_inotify_finish_control(_root)
            original_fd = watch.fd

            def failing_read_events():
                events.append("inotify-read")
                raise RuntimeError("inotify read control")

            monkeypatch.setattr(watch, "read_events", failing_read_events)
            real_inotify_controls.append((watch, original_fd))
            return watch
        return OptionalInotifyControl()

    monkeypatch.setattr(
        sys.modules[__name__],
        "_task5a_required_success_strace_observer",
        required_strace_control,
    )
    monkeypatch.setattr(
        sys.modules[__name__],
        "_task5a_optional_inotify_observer",
        optional_inotify_control,
    )
    if failure_stage in {
        "directory-fd-acquisition",
        "precaused-body-and-inotify",
    }:
        def failing_directory_open(*_args, **_kwargs):
            message = (
                "body acquisition control"
                if failure_stage == "precaused-body-and-inotify"
                else "directory fd acquisition control"
            )
            raise OSError(errno.EMFILE, message)

        monkeypatch.setattr(os, "open", failing_directory_open)
    elif failure_stage == "strace-finish":
        real_open = os.open
        real_close = os.close

        def recording_directory_open(*args, **kwargs):
            descriptor = real_open(*args, **kwargs)
            opened_directory_fds.append(descriptor)
            return descriptor

        def recording_directory_close(descriptor):
            if descriptor in opened_directory_fds:
                closed_directory_fds.append(descriptor)
            real_close(descriptor)

        monkeypatch.setattr(os, "open", recording_directory_open)
        monkeypatch.setattr(os, "close", recording_directory_close)

    expected_error = {
        "optional-observer-acquisition": "optional observer acquisition control",
        "directory-fd-acquisition": "directory fd acquisition control",
        "strace-finish": "strace finish control",
        "both-finishes": "strace finish control",
        "precaused-body-and-inotify": "strace finish control",
        "inotify-read-failure": "inotify read control",
    }[failure_stage]
    try:
        with pytest.raises(
            (OSError, AssertionError, RuntimeError),
            match=expected_error,
        ) as exception_info:
            test_task5a_live_strace_observer_proves_noreplace_hidden_directory_move(
                tmp_path
            )
        if failure_stage == "both-finishes":
            assert str(exception_info.value.__cause__) == "inotify finish control"
        elif failure_stage == "precaused-body-and-inotify":
            _task5a_assert_observer_teardown_failures_reachable(
                exception_info.value,
                {
                    ("RuntimeError", "preexisting strace cause control"),
                    ("AssertionError", "inotify finish control"),
                    (
                        "OSError",
                        f"[Errno {errno.EMFILE}] body acquisition control",
                    ),
                },
            )
        elif failure_stage == "inotify-read-failure":
            watch, original_fd = real_inotify_controls[0]
            assert type(exception_info.value) is RuntimeError
            assert str(exception_info.value) == "inotify read control"
            assert watch.fd == -1
            with pytest.raises(OSError) as fd_error:
                os.fstat(original_fd)
            assert fd_error.value.errno == errno.EBADF
    finally:
        for watch, _original_fd in real_inotify_controls:
            if watch.fd >= 0:
                watch.close()

    expected_events = [
        "strace-acquired",
        "inotify-acquisition",
        "strace-finish",
    ]
    if failure_stage == "inotify-read-failure":
        expected_events.append("inotify-read")
    elif failure_stage != "optional-observer-acquisition":
        expected_events.append("inotify-finish")
    assert events == expected_events
    assert opened_directory_fds == closed_directory_fds
    assert _task5a_tracer_pid() == 0


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux observer")
def test_task5a_live_strace_observer_proves_noreplace_hidden_directory_move(
    tmp_path,
):
    cache_root = tmp_path / "source-cache"
    cache_root.mkdir()
    staging = cache_root / ".task5a-observer-control"
    staging.mkdir()
    target = cache_root / "published-control"

    observer = _task5a_required_success_strace_observer(
        cache_root,
        tmp_path / "task5a-observer-control.strace",
    )
    visibility_observer = None
    visibility_observation = None
    directory_fd = None
    try:
        try:
            visibility_observer = _task5a_optional_inotify_observer(cache_root)
            directory_fd = os.open(
                cache_root,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC,
            )
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = getattr(libc, "renameat2", None)
            rename_arguments = (
                directory_fd,
                os.fsencode(staging.name),
                directory_fd,
                os.fsencode(target.name),
                1,
            )
            if renameat2 is not None:
                renameat2.argtypes = [
                    ctypes.c_int,
                    ctypes.c_char_p,
                    ctypes.c_int,
                    ctypes.c_char_p,
                    ctypes.c_uint,
                ]
                renameat2.restype = ctypes.c_int
                result = renameat2(*rename_arguments)
            else:
                syscall_number = {
                    "x86_64": 316,
                    "aarch64": 276,
                }.get(os.uname().machine)
                if syscall_number is None:
                    pytest.fail("live Linux renameat2 control is unavailable")
                libc.syscall.restype = ctypes.c_long
                result = libc.syscall(syscall_number, *rename_arguments)
            if result != 0:
                pytest.fail("live Linux renameat2 no-replace control failed")
        finally:
            if directory_fd is not None:
                os.close(directory_fd)
    finally:
        observation, visibility_observation = (
            _task5a_finish_strace_then_optional_inotify(
                observer,
                visibility_observer,
            )
        )

    checkpoint_records = [
        record
        for record in observation["records"]
        if record["operation"] in {"open", "openat"}
        and any(
            path.name.startswith(TASK5A_STRACE_CHECKPOINT_PREFIX)
            for path in record["paths"]
        )
    ]
    assert len(checkpoint_records) == 1, checkpoint_records
    assert "ENOSYS" not in checkpoint_records[0]["line"]
    if visibility_observation is not None:
        visible_staging_name, visibility_cookie = (
            _task5a_assert_single_directory_publication(
                visibility_observation["events"],
                target.name,
            )
        )
    staging_name, publication_proof = _task5a_assert_successful_publication(
        observation,
        cache_root,
        target,
    )
    assert staging_name == ".task5a-observer-control"
    if visibility_observation is not None:
        assert visible_staging_name == staging_name
        assert visibility_cookie != 0
    assert publication_proof != 0
    assert target.is_dir() and not target.is_symlink()


@pytest.mark.parametrize(
    "operation",
    ("io.open", "builtins.open", "os.open"),
)
def test_task5a_exclusive_write_fault_harness_accepts_low_level_writer(
    tmp_path,
    monkeypatch,
    operation,
):
    cache_root = tmp_path / "source-cache"
    staging = cache_root / ".invocation-owned-staging"
    staging.mkdir(parents=True)
    destination = staging / "source.pdf"
    events = []
    faults = _task5a_install_exclusive_write_fault(
        monkeypatch,
        cache_root=cache_root,
        basename=destination.name,
        error_number=errno.EIO,
        event_name="exclusive-payload-write-fault",
        events=events,
    )

    with pytest.raises(OSError) as raised:
        if operation == "io.open":
            io.open(destination, "xb")
        elif operation == "builtins.open":
            builtins.open(destination, "xb")
        else:
            os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL)

    assert raised.value.errno == errno.EIO
    assert events == ["exclusive-payload-write-fault"]
    assert len(faults) == 1
    assert faults[0]["operation"] == operation
    assert faults[0]["path"] == destination
    assert not os.path.lexists(destination)


class _Task5ANonJsonBibliographicProbe:
    def __init__(self, marker):
        self.marker = marker

    def __eq__(self, other):
        return (
            isinstance(other, _Task5ANonJsonBibliographicProbe)
            and other.marker == self.marker
        )


def test_task5a_nonserializable_bibliographic_structure_reaches_real_provenance():
    fixture = _task5a_lifecycle_fixture()
    bibliographic = copy.deepcopy(fixture["bibliographic"])
    nonserializable_probe = _Task5ANonJsonBibliographicProbe(
        "distinctive-task5a-provenance-serialization-probe"
    )
    bibliographic["task5a_nonserializable_probe"] = nonserializable_probe
    route = fixture["route"]
    response = {
        "body": fixture["primary_payload"],
        "final_url": route["authoritative_retrieval_route"]["url"],
        "headers": {"content-type": "application/pdf"},
        "media_type": "application/pdf",
        "status": 200,
    }

    provenance = source_fetcher._build_provenance(
        fixture["source"],
        route,
        response,
        bibliographic,
        payload_name="source.pdf",
    )

    propagated_probe = provenance["bibliographic_metadata"][
        "task5a_nonserializable_probe"
    ]
    if not isinstance(propagated_probe, _Task5ANonJsonBibliographicProbe):
        pytest.fail("non-JSON bibliographic probe type was not preserved")
    if propagated_probe.marker != nonserializable_probe.marker:
        pytest.fail("non-JSON bibliographic probe meaning was not preserved")
    with pytest.raises(TypeError) as serialization_error:
        json.dumps(
            provenance,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
    serialization_reason = str(serialization_error.value)
    if (
        "_Task5ANonJsonBibliographicProbe" not in serialization_reason
        or "not JSON serializable" not in serialization_reason
    ):
        pytest.fail("real JSON serialization rejected the probe for the wrong reason")


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
    filesystem_faults = None
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
    elif failure_stage == "provenance-serialization":
        bibliographic = copy.deepcopy(bibliographic)
        bibliographic["task5a_nonserializable_probe"] = (
            _Task5ANonJsonBibliographicProbe(
                "distinctive-task5a-lifecycle-cleanup-probe"
            )
        )

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
    elif failure_stage in {"exclusive-payload-write", "exclusive-sidecar-write"}:
        basename, error_number, event_name = {
            "exclusive-payload-write": (
                "source.pdf",
                errno.EIO,
                "exclusive-payload-write-fault",
            ),
            "exclusive-sidecar-write": (
                "work-identity.json",
                errno.ENOSPC,
                "exclusive-sidecar-write-fault",
            ),
        }[failure_stage]
        filesystem_faults = _task5a_install_exclusive_write_fault(
            monkeypatch,
            cache_root=cache_root,
            basename=basename,
            error_number=error_number,
            event_name=event_name,
            events=events,
        )
    elif failure_stage == "offline-candidate-replay":
        real_loader = source_fetcher.load_verified_source

        def replay_candidate(candidate, **kwargs):
            candidate = Path(candidate)
            events.append("offline-replay-enter")
            _task5a_assert_complete_hal_candidate(candidate, fixture)
            payload_path = candidate / "source.pdf"
            original_payload = payload_path.read_bytes()
            payload_path.write_bytes(
                original_payload + b"INJECTED-OFFLINE-REPLAY-MUTATION"
            )
            assert payload_path.read_bytes() != original_payload
            events.append("offline-primary-payload-mutated")
            return real_loader(candidate, **kwargs)

        monkeypatch.setattr(source_fetcher, "load_verified_source", replay_candidate)

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
        if failure_stage == "provenance-serialization":
            _task5a_assert_inputs_complete(events)
            if (
                "_Task5ANonJsonBibliographicProbe" not in outcome["detail"]
                or "not JSON serializable" not in outcome["detail"]
            ):
                pytest.fail("lifecycle serialization failed for the wrong reason")
        else:
            terminal_event = {
                "provenance-build": "provenance-build-enter",
                "exclusive-payload-write": "exclusive-payload-write-fault",
                "exclusive-sidecar-write": "exclusive-sidecar-write-fault",
                "offline-candidate-replay": "offline-replay-enter",
            }[failure_stage]
            _task5a_assert_inputs_complete_before(events, terminal_event)
        if failure_stage == "provenance-build":
            assert str(failure) in outcome["detail"]
        elif failure_stage in {"exclusive-payload-write", "exclusive-sidecar-write"}:
            assert filesystem_faults is not None
            assert len(filesystem_faults) == 1
            fault = filesystem_faults[0]
            assert fault["operation"] in {"io.open", "builtins.open", "os.open"}
            assert fault["path"].name in {"source.pdf", "work-identity.json"}
            assert fault["path"].parent.parent == cache_root
            assert fault["path"].parent.name.startswith(".")
            assert os.strerror(fault["errno"]) in outcome["detail"]
    if failure_stage == "offline-candidate-replay":
        _task5a_assert_event_order(
            events,
            "offline-replay-enter",
            "offline-primary-payload-mutated",
            "offline-hal-crossref-validator-enter",
            "offline-hal-crossref-validator-complete",
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
    replayed_candidates = []
    _task5a_install_real_lifecycle_boundary(
        monkeypatch,
        fixture,
        events=events,
        target=target,
        target_visibility=target_visibility,
    )
    real_loader = source_fetcher.load_verified_source

    def replay_candidate(candidate, **kwargs):
        candidate = Path(os.path.abspath(candidate))
        events.append("offline-replay-enter")
        target_visible_before_replay = target.exists() or target.is_symlink()
        _task5a_assert_complete_hal_candidate(candidate, fixture)
        verified = real_loader(candidate, **kwargs)
        assert candidate != target
        assert candidate.parent == cache_root
        assert target_visible_before_replay is False
        assert candidate.joinpath("source.pdf").is_file()
        assert candidate.joinpath("provenance.json").is_file()
        assert candidate.joinpath("work-identity.json").is_file()
        assert candidate.joinpath("work-identity.provenance.json").is_file()
        assert not target.exists() and not target.is_symlink()
        candidate_status = candidate.lstat()
        replayed_candidates.append(
            {
                "path": candidate,
                "directory_identity": (
                    candidate_status.st_dev,
                    candidate_status.st_ino,
                ),
                "root_mode": candidate_status.st_mode,
                "manifest": _task5a_cache_manifest(candidate),
            }
        )
        events.append("offline-replay-complete")
        replayed.append(verified)
        return verified

    monkeypatch.setattr(source_fetcher, "load_verified_source", replay_candidate)

    observer = _task5a_required_success_strace_observer(
        cache_root,
        tmp_path / "task5a-success-publication.strace",
    )
    visibility_observer = None
    visibility_observation = None
    try:
        visibility_observer = _task5a_optional_inotify_observer(cache_root)
        outcome = source_fetcher._fetch_source(
            cache_root,
            source,
            route,
            ca_bundle=Path("/unused"),
            resume=False,
        )
    finally:
        publication_observation, visibility_observation = (
            _task5a_finish_strace_then_optional_inotify(
                observer,
                visibility_observer,
            )
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
    assert len(replayed_candidates) == 1
    assert replayed[0].source_id == source["source_id"]
    assert not any(visible for _event, visible in target_visibility)
    if visibility_observation is not None:
        visible_staging_name, visibility_cookie = (
            _task5a_assert_single_directory_publication(
                visibility_observation["events"],
                target.name,
            )
        )
    staging_name, publication_proof = (
        _task5a_assert_successful_publication(
            publication_observation,
            cache_root,
            target,
        )
    )
    assert publication_proof != 0
    replayed_candidate = replayed_candidates[0]
    publication_record = next(
        record
        for record in publication_observation["records"]
        if record["line_number"] == publication_proof
    )
    publication_source, publication_target = _task5a_strace_rename_paths(
        publication_record
    )
    if publication_source != replayed_candidate["path"]:
        pytest.fail("published directory was not the replay-validated candidate")
    if publication_target != target:
        pytest.fail("validated candidate was published to an unexpected target")
    if visibility_observation is not None:
        assert visible_staging_name == staging_name
        assert visibility_cookie != 0
    assert staging_name != foreign_staging.name
    assert not os.path.lexists(cache_root / staging_name)
    assert not os.path.lexists(replayed_candidate["path"])
    assert target.is_dir() and not target.is_symlink()
    target_status = target.lstat()
    if (target_status.st_dev, target_status.st_ino) != replayed_candidate[
        "directory_identity"
    ]:
        pytest.fail("published target is not the replay-validated directory object")
    if target_status.st_mode != replayed_candidate["root_mode"]:
        pytest.fail("published target root mode changed after offline replay")
    if _task5a_cache_manifest(target) != replayed_candidate["manifest"]:
        pytest.fail("published target differs from the replay-validated candidate")
    assert {path.name for path in cache_root.iterdir()} == {
        ".foreign-operation-staging",
        "preexisting_source",
        source["source_id"],
    }
    assert _task5a_cache_manifest(existing) == before_existing
    assert _task5a_cache_manifest(foreign_staging) == before_foreign_staging


@pytest.mark.parametrize(
    "failure_stage",
    (
        "optional-observer-acquisition",
        "strace-finish",
        "both-finishes",
        "precaused-body-and-inotify",
        pytest.param(
            "inotify-read-failure",
            marks=pytest.mark.skipif(
                sys.platform != "linux",
                reason="requires Linux inotify",
            ),
        ),
    ),
)
def test_task5a_public_success_teardown_reaps_strace_then_closes_optional_observer(
    tmp_path,
    monkeypatch,
    failure_stage,
):
    events = []
    real_inotify_controls = []

    class RequiredStraceControl:
        def finish(self):
            events.append("strace-finish")
            if failure_stage == "precaused-body-and-inotify":
                raise AssertionError(
                    "public success strace finish control"
                ) from RuntimeError(
                    "public success preexisting strace cause control"
                )
            if failure_stage in {"strace-finish", "both-finishes"}:
                raise AssertionError("public success strace finish control")
            return {"backend": "strace", "records": [], "payload": ""}

    class OptionalInotifyControl:
        def finish(self):
            events.append("inotify-finish")
            if failure_stage in {
                "both-finishes",
                "precaused-body-and-inotify",
            }:
                raise AssertionError("public success inotify finish control")
            return {"backend": "inotify", "events": []}

    def required_strace_control(_root, _trace_path):
        events.append("strace-acquired")
        return RequiredStraceControl()

    def optional_inotify_control(_root):
        events.append("inotify-acquisition")
        if failure_stage == "optional-observer-acquisition":
            raise OSError(
                errno.EIO,
                "public success optional observer acquisition control",
            )
        if failure_stage == "inotify-read-failure":
            watch = _task5a_unwatched_inotify_finish_control(_root)
            original_fd = watch.fd

            def failing_read_events():
                events.append("inotify-read")
                raise RuntimeError("public success inotify read control")

            monkeypatch.setattr(watch, "read_events", failing_read_events)
            real_inotify_controls.append((watch, original_fd))
            return watch
        return OptionalInotifyControl()

    monkeypatch.setattr(
        sys.modules[__name__],
        "_task5a_required_success_strace_observer",
        required_strace_control,
    )
    monkeypatch.setattr(
        sys.modules[__name__],
        "_task5a_optional_inotify_observer",
        optional_inotify_control,
    )
    if failure_stage == "precaused-body-and-inotify":
        def failing_fetch_source(*_args, **_kwargs):
            raise RuntimeError("public success body control")

        monkeypatch.setattr(
            source_fetcher,
            "_fetch_source",
            failing_fetch_source,
        )

    expected_error = {
        "optional-observer-acquisition": (
            "public success optional observer acquisition control"
        ),
        "strace-finish": "public success strace finish control",
        "both-finishes": "public success strace finish control",
        "precaused-body-and-inotify": (
            "public success strace finish control"
        ),
        "inotify-read-failure": "public success inotify read control",
    }[failure_stage]
    try:
        with pytest.raises(
            (OSError, AssertionError, RuntimeError),
            match=expected_error,
        ) as exception_info:
            test_task5a_success_publishes_complete_target_only_after_real_offline_replay(
                tmp_path,
                monkeypatch,
            )
        if failure_stage == "both-finishes":
            assert str(exception_info.value.__cause__) == (
                "public success inotify finish control"
            )
        elif failure_stage == "precaused-body-and-inotify":
            _task5a_assert_observer_teardown_failures_reachable(
                exception_info.value,
                {
                    (
                        "RuntimeError",
                        "public success preexisting strace cause control",
                    ),
                    (
                        "AssertionError",
                        "public success inotify finish control",
                    ),
                    ("RuntimeError", "public success body control"),
                },
            )
        elif failure_stage == "inotify-read-failure":
            watch, original_fd = real_inotify_controls[0]
            assert type(exception_info.value) is RuntimeError
            assert str(exception_info.value) == (
                "public success inotify read control"
            )
            assert watch.fd == -1
            with pytest.raises(OSError) as fd_error:
                os.fstat(original_fd)
            assert fd_error.value.errno == errno.EBADF
    finally:
        for watch, _original_fd in real_inotify_controls:
            if watch.fd >= 0:
                watch.close()

    expected_events = [
        "strace-acquired",
        "inotify-acquisition",
        "strace-finish",
    ]
    if failure_stage == "inotify-read-failure":
        expected_events.append("inotify-read")
    elif failure_stage in {
        "strace-finish",
        "both-finishes",
        "precaused-body-and-inotify",
    }:
        expected_events.append("inotify-finish")
    assert events == expected_events
    assert _task5a_tracer_pid() == 0


@pytest.mark.parametrize(
    "collision_kind",
    (
        "empty-directory",
        "nonempty-directory",
        "regular-file",
        "dangling-symlink",
    ),
)
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
    collision_snapshots = []
    replayed_candidates = []
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
        assert candidate.parent == cache_root
        assert candidate.name.startswith(".")
        assert target_visible_before_replay is False
        assert not target.exists() and not target.is_symlink()
        replayed_candidates.append(candidate)
        if collision_kind in {"empty-directory", "nonempty-directory"}:
            target.mkdir()
        elif collision_kind == "regular-file":
            target.write_bytes(b"CONCURRENT-REGULAR-FILE")
        else:
            assert collision_kind == "dangling-symlink"
            target.symlink_to("missing-concurrent-target")
        if collision_kind == "nonempty-directory":
            target.joinpath("sentinel").write_bytes(b"CONCURRENT-TARGET")
            target.joinpath("nested").mkdir()
            target.joinpath("nested", "payload").write_bytes(
                b"CONCURRENT-NESTED-PAYLOAD"
            )
        collision_snapshots.append(_round7_tree_snapshot(target))
        events.append(f"concurrent-{collision_kind}-target-created")
        return verified

    monkeypatch.setattr(
        source_fetcher,
        "load_verified_source",
        replay_then_create_collision,
    )
    observer = _task5a_publication_observer_or_skip(
        cache_root,
        tmp_path / f"task5a-{collision_kind}-collision.strace",
    )
    try:
        outcome = source_fetcher._fetch_source(
            cache_root,
            source,
            route,
            ca_bundle=Path("/unused"),
            resume=False,
        )
    finally:
        publication_observation = observer.finish()

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
    assert len(collision_snapshots) == 1
    assert len(replayed_candidates) == 1
    assert os.path.lexists(target)
    assert _round7_tree_snapshot(target) == collision_snapshots[0]
    staging_name = _task5a_assert_failed_collision_publication(
        publication_observation,
        cache_root,
        target,
        candidate=replayed_candidates[0],
        foreign_staging=foreign_staging,
    )
    assert staging_name != foreign_staging.name
    assert not any(visible for _event, visible in target_visibility)
    assert _task5a_cache_manifest(existing) == before_existing
    assert _task5a_cache_manifest(foreign_staging) == before_foreign_staging
    assert {path.name for path in cache_root.iterdir()} == {
        ".foreign-operation-staging",
        "preexisting_source",
        source["source_id"],
    }


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux observer")
def test_task5a_live_strace_observer_rejects_early_death_and_detaches(tmp_path):
    read_fd, write_fd = os.pipe()
    child_pid = os.fork()
    if child_pid == 0:
        os.close(read_fd)
        child_result = {}
        child_exit_code = 0
        try:
            cache_root = tmp_path / "early-death-child-source-cache"
            cache_root.mkdir()
            observer = _task5a_required_success_strace_observer(
                cache_root,
                tmp_path / "task5a-observer-early-death.strace",
            )
            if not observer._await_completed_checkpoint():
                raise AssertionError("early-death partial trace control was incomplete")
            observer.process.kill()
            observer.process.communicate(timeout=5)
            deadline = time.monotonic() + 5.0
            while _task5a_tracer_pid() != 0 and time.monotonic() < deadline:
                time.sleep(0.01)
            try:
                observer.finish()
            except AssertionError as error:
                partial_records = _task5a_parse_strace_payload(
                    observer.trace_path.read_text(encoding="utf-8")
                )
                child_result = {
                    "error": str(error),
                    "partial_trace_parsed": bool(partial_records),
                    "returncode": observer.process.returncode,
                    "tracer_pid": _task5a_tracer_pid(),
                }
            else:
                child_result = {"unexpected": "early death was accepted"}
                child_exit_code = 1
        except BaseException as error:
            child_result = {
                "unexpected_type": type(error).__name__,
                "unexpected_error": str(error),
            }
            child_exit_code = 1
        encoded_result = json.dumps(child_result, sort_keys=True).encode("utf-8")
        try:
            os.write(write_fd, encoded_result)
        finally:
            os.close(write_fd)
        os._exit(child_exit_code)

    os.close(write_fd)
    child_payload = bytearray()
    try:
        while True:
            chunk = os.read(read_fd, 4096)
            if not chunk:
                break
            child_payload.extend(chunk)
    finally:
        os.close(read_fd)
    waited_pid, child_status = os.waitpid(child_pid, 0)
    assert waited_pid == child_pid
    assert os.WIFEXITED(child_status)
    assert os.WEXITSTATUS(child_status) == 0
    assert json.loads(child_payload) == {
        "error": TASK5A_STRACE_EARLY_DEATH,
        "partial_trace_parsed": True,
        "returncode": -signal.SIGKILL,
        "tracer_pid": 0,
    }

    normal_root = tmp_path / "post-early-death-normal-source-cache"
    normal_root.mkdir()
    normal_observer = _task5a_required_success_strace_observer(
        normal_root,
        tmp_path / "task5a-post-early-death-normal.strace",
    )
    normal_observation = normal_observer.finish()
    assert TASK5A_STRACE_CHECKPOINT_PREFIX in normal_observation["payload"]
    assert normal_observer.process.returncode == 0
    assert _task5a_tracer_pid() == 0


def _task5a_assert_no_forbidden_query_channels(
    *,
    forbidden,
    outcome=None,
    exception=None,
    caplog,
    capsys,
    cache_root,
):
    def exception_tree(error, seen=None):
        if error is None:
            return None
        seen = set() if seen is None else seen
        if id(error) in seen:
            return {"cycle": type(error).__name__}
        seen.add(id(error))
        return {
            "type": type(error).__name__,
            "str": str(error),
            "repr": repr(error),
            "args": error.args,
            "attributes": vars(error),
            "cause": exception_tree(error.__cause__, seen),
            "context": exception_tree(error.__context__, seen),
        }

    cache_root = Path(cache_root)
    cache_entries = []
    if os.path.lexists(cache_root):
        for path in sorted(cache_root.rglob("*")):
            entry = {"path": path.relative_to(cache_root).as_posix()}
            if path.is_symlink():
                entry.update({"kind": "symlink", "target": os.readlink(path)})
            elif path.is_file():
                entry.update({"kind": "file", "payload": path.read_bytes()})
            else:
                entry["kind"] = "directory"
            cache_entries.append(entry)
    captured = capsys.readouterr()
    channels = {
        "exception": exception_tree(exception),
        "outcome": outcome,
        "outcome_json": (
            json.dumps(outcome, sort_keys=True, ensure_ascii=True)
            if outcome is not None
            else None
        ),
        "logs": {
            "rendered": caplog.text,
            "records": [
                {
                    "message": record.getMessage(),
                    "raw_message": record.msg,
                    "args": record.args,
                    "attributes": record.__dict__,
                    "exception": exception_tree(
                        record.exc_info[1] if record.exc_info else None
                    ),
                }
                for record in caplog.records
            ],
        },
        "stdout": captured.out,
        "stderr": captured.err,
        "cache": cache_entries,
    }
    if "1" in forbidden or "0" in forbidden:
        pytest.fail("forbidden query set contains an overbroad numeric value")
    leaking_channels = {
        channel_name
        for channel_name, channel in channels.items()
        if any(
            secret.casefold() in rendered.casefold()
            for rendered in _recursive_strings(channel)
            for secret in forbidden
        )
    }
    assert not leaking_channels, (
        "forbidden query material leaked through external channels: "
        + ", ".join(sorted(leaking_channels))
    )
    if outcome is not None:
        assert outcome["status"] == "failed"
        assert isinstance(outcome["detail"], str) and outcome["detail"].strip()


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


def _task5a_hal_forbidden_query_material():
    q_expression = dict(TASK5A_HAL_QUERY_PAIRS)["q"]
    auxiliary_pair_fragments = tuple(
        fragment
        for key, value in TASK5A_HAL_QUERY_PAIRS
        if key in {"rows", "start", "wt"}
        for fragment in (
            f"{key}={value}",
            quote_plus(f"{key}={value}", safe=""),
        )
    )
    return (
        TASK5A_HAL_REQUEST_URL,
        TASK5A_HAL_QUERY,
        unquote_plus(TASK5A_HAL_QUERY),
        q_expression,
        quote_plus(q_expression, safe=""),
        TASK5A_HAL_FIELD_PROJECTION,
        quote_plus(TASK5A_HAL_FIELD_PROJECTION, safe=""),
    ) + auxiliary_pair_fragments


def test_task5a_hal_forbidden_material_covers_exact_auxiliary_query_pairs():
    forbidden = set(_task5a_hal_forbidden_query_material())
    expected_fragments = {
        fragment
        for key, value in (("rows", "1"), ("start", "0"), ("wt", "json"))
        for fragment in (
            f"{key}={value}",
            quote_plus(f"{key}={value}", safe=""),
        )
    }
    if not expected_fragments <= forbidden:
        pytest.fail("HAL auxiliary query-pair redaction coverage is incomplete")
    if {"0", "1"} & forbidden:
        pytest.fail("HAL query-pair redaction coverage is overbroad")


def test_task5a_hal_sidecar_open_failure_redacts_every_external_channel(
    tmp_path,
    monkeypatch,
    caplog,
    capsys,
):
    cache_root = tmp_path / "source-cache"
    preexisting = cache_root / "preexisting_source"
    preexisting.mkdir(parents=True)
    preexisting.joinpath("sentinel").write_bytes(b"UNCHANGED")
    before = _task5a_cache_manifest(cache_root)
    fixture = _task5a_lifecycle_fixture()
    source = fixture["source"]
    route = copy.deepcopy(fixture["route"])
    assert route["authoritative_retrieval_route"]["work_identity_evidence"][
        "url"
    ] == TASK5A_HAL_BASE
    target = cache_root / source["source_id"]
    requests = []

    class FixtureOpener:
        def open(self, request, timeout):
            requests.append(request.full_url)
            if _header_dict(request).get("accept") == "application/pdf":
                return _FixtureHTTPResponse(
                    fixture["primary_payload"],
                    content_type="application/pdf",
                    final_url=route["authoritative_retrieval_route"]["url"],
                )
            raise OSError("HAL sidecar transport failed at " + request.full_url)

    monkeypatch.setattr(source_fetcher, "_ssl_context", lambda _path: object())
    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )
    monkeypatch.setattr(
        source_fetcher,
        "_fetch_bibliographic_metadata",
        lambda *args, **kwargs: copy.deepcopy(fixture["bibliographic"]),
    )

    outcome = source_fetcher._fetch_source(
        cache_root,
        source,
        route,
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert requests == [
        route["authoritative_retrieval_route"]["url"],
        TASK5A_HAL_REQUEST_URL,
    ]
    assert route["authoritative_retrieval_route"]["work_identity_evidence"][
        "url"
    ] == TASK5A_HAL_BASE
    assert "HAL sidecar transport failed" in outcome["detail"]
    _task5a_assert_no_forbidden_query_channels(
        forbidden=_task5a_hal_forbidden_query_material(),
        outcome=outcome,
        caplog=caplog,
        capsys=capsys,
        cache_root=cache_root,
    )
    assert not os.path.lexists(target)
    assert not any(path.name.startswith(".") for path in cache_root.iterdir())
    assert _task5a_cache_manifest(cache_root) == before
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


# Task 5A.2 review controls: close the HAL cache publication boundary without
# changing the compatibility contract for older, non-HAL evidence sidecars.


def _task5a_run_lifecycle(cache_root, monkeypatch, fixture):
    events = []
    target = cache_root / fixture["source"]["source_id"]
    _task5a_install_real_lifecycle_boundary(
        monkeypatch,
        fixture,
        events=events,
        target=target,
        target_visibility=[],
    )
    outcome = source_fetcher._fetch_source(
        cache_root,
        fixture["source"],
        fixture["route"],
        ca_bundle=Path("/unused"),
        resume=False,
    )
    return target, outcome


def test_task5a_hal_offline_candidate_requires_descriptor_media_type(
    tmp_path,
    monkeypatch,
):
    cache_root = tmp_path / "source-cache"
    existing = cache_root / "existing"
    existing.mkdir(parents=True)
    existing.joinpath("sentinel").write_bytes(b"UNCHANGED")
    before = _task5a_cache_manifest(cache_root)
    fixture = _task5a_lifecycle_fixture()
    real_fetch = source_fetcher._fetch_work_identity_evidence

    def fetch_without_media_type(*args, **kwargs):
        evidence = real_fetch(*args, **kwargs)
        evidence["descriptor"].pop("media_type")
        return evidence

    monkeypatch.setattr(
        source_fetcher,
        "_fetch_work_identity_evidence",
        fetch_without_media_type,
    )
    target, outcome = _task5a_run_lifecycle(cache_root, monkeypatch, fixture)

    assert outcome["status"] == "failed", outcome
    assert "media_type" in outcome["detail"]
    assert not os.path.lexists(target)
    assert _task5a_cache_manifest(cache_root) == before


def test_task5a_legacy_json_sidecar_without_media_type_remains_accepted(tmp_path):
    source_dir, route = _repository_fixture(tmp_path)
    descriptor = json.loads(
        source_dir.joinpath("provenance.json").read_text(encoding="utf-8")
    )["retrieval_metadata"]["work_identity_evidence"]
    assert "media_type" not in descriptor
    verified = load_verified_source(
        source_dir,
        expected_source=_expected_source(),
        provisioning_route=route,
    )
    assert verified.source_id == SOURCE_ID


def test_task5a_first_staging_identity_failure_cleans_created_candidate(
    tmp_path,
    monkeypatch,
):
    cache_root = tmp_path / "source-cache"
    existing = cache_root / "existing"
    existing.mkdir(parents=True)
    existing.joinpath("sentinel").write_bytes(b"UNCHANGED")
    before = _task5a_cache_manifest(cache_root)
    fixture = _task5a_lifecycle_fixture()
    real_path_lstat = Path.lstat
    real_os_stat = os.stat
    faults = []

    def is_staging(path):
        return Path(path).name.startswith(".literature-evidence-staging-")

    def faulting_path_lstat(path, *args, **kwargs):
        if not faults and is_staging(path):
            faults.append("Path.lstat")
            raise OSError(errno.EIO, os.strerror(errno.EIO), path)
        return real_path_lstat(path, *args, **kwargs)

    def faulting_os_stat(path, *args, **kwargs):
        if not faults and is_staging(path):
            faults.append("os.stat")
            raise OSError(errno.EIO, os.strerror(errno.EIO), path)
        return real_os_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", faulting_path_lstat)
    monkeypatch.setattr(os, "stat", faulting_os_stat)
    target, outcome = _task5a_run_lifecycle(cache_root, monkeypatch, fixture)

    assert len(faults) == 1
    assert outcome["status"] == "failed", outcome
    assert os.strerror(errno.EIO) in outcome["detail"]
    assert not os.path.lexists(target)
    assert _task5a_cache_manifest(cache_root) == before


@pytest.mark.parametrize("failure_stage", ("staging-open", "staging-fstat"))
def test_task5a_post_mkdir_staging_allocation_failure_cleans_created_candidate(
    tmp_path,
    monkeypatch,
    failure_stage,
):
    cache_root = tmp_path / "source-cache"
    existing = cache_root / "existing"
    existing.mkdir(parents=True)
    existing.joinpath("sentinel").write_bytes(b"UNCHANGED")
    before = _task5a_cache_manifest(cache_root)
    fixture = _task5a_lifecycle_fixture()
    real_open = os.open
    real_fstat = os.fstat
    staging_descriptors = set()
    faults = []

    def is_staging_name(path):
        return Path(os.fsdecode(path)).name.startswith(
            ".literature-evidence-staging-"
        )

    def faulting_open(path, flags, mode=0o777, *, dir_fd=None):
        if (
            failure_stage == "staging-open"
            and not faults
            and dir_fd is not None
            and is_staging_name(path)
            and flags & os.O_DIRECTORY
        ):
            faults.append("staging-open")
            raise OSError(errno.EIO, os.strerror(errno.EIO), path)
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        if (
            dir_fd is not None
            and is_staging_name(path)
            and flags & os.O_DIRECTORY
        ):
            staging_descriptors.add(descriptor)
        return descriptor

    def faulting_fstat(descriptor):
        if (
            failure_stage == "staging-fstat"
            and not faults
            and descriptor in staging_descriptors
        ):
            faults.append("staging-fstat")
            raise OSError(errno.EIO, os.strerror(errno.EIO), descriptor)
        return real_fstat(descriptor)

    monkeypatch.setattr(os, "open", faulting_open)
    monkeypatch.setattr(os, "fstat", faulting_fstat)
    target, outcome = _task5a_run_lifecycle(cache_root, monkeypatch, fixture)

    assert faults == [failure_stage]
    assert outcome["status"] == "failed", outcome
    assert os.strerror(errno.EIO) in outcome["detail"]
    assert not os.path.lexists(target)
    assert not any(cache_root.glob(".literature-evidence-staging-*"))
    assert _task5a_cache_manifest(cache_root) == before


def test_task5a_cleanup_rejects_nested_child_replacement_before_traversal(
    tmp_path,
    monkeypatch,
):
    candidate = tmp_path / "owned-candidate"
    owned_child = candidate / "nested-child"
    owned_child.mkdir(parents=True)
    owned_child.joinpath("owned-sentinel").write_bytes(b"OWNED")
    displaced_child = tmp_path / "displaced-owned-child"
    foreign_child = tmp_path / "foreign-child"
    foreign_child.mkdir()
    foreign_child.joinpath("foreign-sentinel").write_bytes(b"FOREIGN")
    directory_fd = os.open(
        candidate,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    real_open = os.open
    swaps = []

    def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
        if (
            not swaps
            and dir_fd == directory_fd
            and os.fsdecode(path) == owned_child.name
            and flags & os.O_DIRECTORY
        ):
            owned_child.rename(displaced_child)
            foreign_child.rename(owned_child)
            swaps.append(owned_child)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", swapping_open)
    try:
        with pytest.raises(SourceEvidenceError, match="staging child changed"):
            source_fetcher._remove_directory_contents_fd(directory_fd)
    finally:
        os.close(directory_fd)

    assert swaps == [owned_child]
    assert owned_child.joinpath("foreign-sentinel").read_bytes() == b"FOREIGN"
    assert displaced_child.joinpath("owned-sentinel").read_bytes() == b"OWNED"


def test_task5a_cache_root_swap_after_real_directory_check_is_fail_closed(
    tmp_path,
    monkeypatch,
):
    cache_root = tmp_path / "source-cache"
    cache_root.mkdir()
    cache_root.joinpath("sentinel").write_bytes(b"ORIGINAL")
    displaced_root = tmp_path / "displaced-cache-root"
    foreign_root = tmp_path / "foreign-cache-root"
    foreign_root.mkdir()
    foreign_root.joinpath("sentinel").write_bytes(b"FOREIGN")
    before_original = _task5a_cache_manifest(cache_root)
    before_foreign = _task5a_cache_manifest(foreign_root)
    fixture = _task5a_lifecycle_fixture()
    real_lstat = Path.lstat
    swaps = []

    def swapping_lstat(path, *args, **kwargs):
        status = real_lstat(path, *args, **kwargs)
        if not swaps and Path(path) == cache_root:
            cache_root.rename(displaced_root)
            cache_root.symlink_to(foreign_root, target_is_directory=True)
            swaps.append((status.st_dev, status.st_ino))
        return status

    monkeypatch.setattr(Path, "lstat", swapping_lstat)
    target, outcome = _task5a_run_lifecycle(cache_root, monkeypatch, fixture)

    assert len(swaps) == 1
    assert outcome["status"] == "failed", outcome
    assert cache_root.is_symlink()
    assert not os.path.lexists(displaced_root / fixture["source"]["source_id"])
    assert not os.path.lexists(foreign_root / fixture["source"]["source_id"])
    assert _task5a_cache_manifest(displaced_root) == before_original
    assert _task5a_cache_manifest(foreign_root) == before_foreign
    assert not os.path.lexists(target)


@pytest.mark.parametrize("replacement_kind", ("directory", "symlink"))
def test_task5a_publish_rejects_same_name_replacement_after_offline_replay(
    tmp_path,
    monkeypatch,
    replacement_kind,
):
    cache_root = tmp_path / "source-cache"
    fixture = _task5a_lifecycle_fixture()
    events = []
    target = cache_root / fixture["source"]["source_id"]
    _task5a_install_real_lifecycle_boundary(
        monkeypatch,
        fixture,
        events=events,
        target=target,
        target_visibility=[],
    )
    foreign = tmp_path / "foreign-candidate"
    foreign.mkdir()
    foreign.joinpath("sentinel").write_bytes(b"FOREIGN")
    displaced = tmp_path / "validated-candidate"
    replacement = []
    real_loader = source_fetcher.load_verified_source

    def replace_after_replay(candidate, **kwargs):
        candidate = Path(candidate)
        verified = real_loader(candidate, **kwargs)
        status = candidate.lstat()
        candidate.rename(displaced)
        if replacement_kind == "directory":
            foreign.rename(candidate)
        else:
            candidate.symlink_to(foreign, target_is_directory=True)
        replacement.append((candidate, (status.st_dev, status.st_ino)))
        return verified

    monkeypatch.setattr(source_fetcher, "load_verified_source", replace_after_replay)
    outcome = source_fetcher._fetch_source(
        cache_root,
        fixture["source"],
        fixture["route"],
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert len(replacement) == 1
    assert outcome["status"] == "failed", outcome
    assert not os.path.lexists(target)
    assert displaced.is_dir()
    replacement_path = replacement[0][0]
    assert replacement_path.is_dir()
    assert replacement_path.joinpath("sentinel").read_bytes() == b"FOREIGN"


def test_task5a_cleanup_does_not_traverse_same_name_foreign_replacement(
    tmp_path,
    monkeypatch,
):
    cache_root = tmp_path / "source-cache"
    fixture = _task5a_lifecycle_fixture()
    events = []
    target = cache_root / fixture["source"]["source_id"]
    _task5a_install_real_lifecycle_boundary(
        monkeypatch,
        fixture,
        events=events,
        target=target,
        target_visibility=[],
    )
    primary = SourceEvidenceError("injected replay failure")
    staging_paths = []

    def fail_replay(candidate, **kwargs):
        staging_paths.append(Path(candidate))
        raise primary

    monkeypatch.setattr(source_fetcher, "load_verified_source", fail_replay)
    foreign = tmp_path / "foreign-cleanup-directory"
    foreign.mkdir()
    foreign.joinpath("sentinel").write_bytes(b"FOREIGN")
    displaced = tmp_path / "owned-cleanup-directory"
    source_shutil = getattr(source_fetcher, "shutil", None)
    real_rmtree = source_shutil.rmtree if source_shutil is not None else None
    real_unlink = os.unlink
    swaps = []

    def swap_replacement():
        if swaps or not staging_paths:
            return
        staging_paths[0].rename(displaced)
        foreign.rename(staging_paths[0])
        swaps.append(staging_paths[0])

    def swapping_rmtree(path, *args, **kwargs):
        swap_replacement()
        return real_rmtree(path, *args, **kwargs)

    def swapping_unlink(path, *args, **kwargs):
        swap_replacement()
        return real_unlink(path, *args, **kwargs)

    if source_shutil is not None:
        monkeypatch.setattr(source_shutil, "rmtree", swapping_rmtree)
    monkeypatch.setattr(os, "unlink", swapping_unlink)
    outcome = source_fetcher._fetch_source(
        cache_root,
        fixture["source"],
        fixture["route"],
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert len(swaps) == 1
    assert outcome["status"] == "failed", outcome
    assert swaps[0].joinpath("sentinel").read_bytes() == b"FOREIGN"
    assert not os.path.lexists(target)


def test_task5a_hal_redirect_is_rejected_before_second_request_or_body_read(
    tmp_path,
    monkeypatch,
    caplog,
    capsys,
):
    query = "hal-redirect-secret=DO-NOT-LEAK"
    redirect_url = "https://api.archives-ouvertes.fr/search/?" + query
    requests = []
    body_reads = []

    class RedirectOpener:
        def __init__(self, handlers):
            self.redirect_handler = next(
                handler for handler in handlers
                if hasattr(handler, "redirect_request")
            )

        def open(self, request, timeout):
            requests.append(request.full_url)
            redirected = self.redirect_handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                redirect_url,
            )
            requests.append(redirected.full_url)

            class TrackingResponse(_FixtureHTTPResponse):
                def read(self):
                    body_reads.append(True)
                    return super().read()

            return TrackingResponse(
                json.dumps(_task5a_hal_document()).encode("utf-8"),
                content_type="application/json",
                final_url=redirected.full_url,
            )

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: RedirectOpener(handlers),
    )
    fixture = _task5a_lifecycle_fixture()
    exposed = None
    try:
        source_fetcher._fetch_work_identity_evidence(
            fixture["source"],
            fixture["route"],
            object(),
            bibliographic_metadata=fixture["bibliographic"],
        )
    except Exception as error:
        exposed = error
    else:
        pytest.fail("HAL redirect was accepted")

    assert len(requests) == 1
    assert body_reads == []
    assert isinstance(exposed, SourceEvidenceError)
    assert "HAL" in str(exposed) and "redirect" in str(exposed).casefold()
    _task5a_assert_no_forbidden_query_channels(
        forbidden=(query, quote_plus(query, safe=""), "DO-NOT-LEAK"),
        exception=exposed,
        caplog=caplog,
        capsys=capsys,
        cache_root=tmp_path / "source-cache",
    )


def test_task5a_generic_redirect_handler_still_follows_safe_redirects():
    request = Request("https://example.invalid/start")
    redirected = source_fetcher._CredentialRedirectHandler(None).redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://example.invalid/final",
    )
    assert redirected.full_url == "https://example.invalid/final"


def _task5a_install_arguments(fixture):
    route = fixture["route"]
    response = {
        "body": fixture["primary_payload"],
        "final_url": route["authoritative_retrieval_route"]["url"],
        "headers": {"content-type": "application/pdf"},
        "media_type": "application/pdf",
        "status": 200,
    }
    provenance = source_fetcher._build_provenance(
        fixture["source"],
        route,
        response,
        fixture["bibliographic"],
        payload_name="source.pdf",
    )
    return {
        "source": fixture["source"],
        "route": route,
        "payload_name": "source.pdf",
        "payload": fixture["primary_payload"],
        "provenance_payload": source_fetcher._serialized_json_bytes(provenance),
        "evidence": {
            "payload": fixture["sidecar_payload"],
            "descriptor": fixture["sidecar_descriptor"],
        },
    }


@pytest.mark.parametrize("primary_stage", ("write", "replay", "publish"))
def test_task5a_cleanup_failure_preserves_primary_exception_and_existing_chain(
    tmp_path,
    monkeypatch,
    primary_stage,
):
    fixture = _task5a_lifecycle_fixture()
    cache_root = tmp_path / "source-cache"
    target = cache_root / fixture["source"]["source_id"]
    primary = SourceEvidenceError("injected primary failure")
    prior_cause = RuntimeError("preexisting cause")
    prior_context = RuntimeError("preexisting context")
    primary.__cause__ = prior_cause
    primary.__context__ = prior_context
    cleanup = OSError(errno.EIO, "injected cleanup failure")

    if primary_stage == "write":
        real_write = source_fetcher._exclusive_write_bytes

        def fail_write(path, payload):
            if Path(path).name == "source.pdf":
                raise primary
            return real_write(path, payload)

        monkeypatch.setattr(source_fetcher, "_exclusive_write_bytes", fail_write)
    elif primary_stage == "replay":
        monkeypatch.setattr(
            source_fetcher,
            "load_verified_source",
            lambda *args, **kwargs: (_ for _ in ()).throw(primary),
        )
    else:
        monkeypatch.setattr(
            source_fetcher,
            "_publish_directory_noreplace",
            lambda *args, **kwargs: (_ for _ in ()).throw(primary),
        )

    real_cleanup = source_fetcher._remove_owned_staging_directory

    def fail_after_cleanup(*args, **kwargs):
        real_cleanup(*args, **kwargs)
        raise cleanup

    monkeypatch.setattr(
        source_fetcher,
        "_remove_owned_staging_directory",
        fail_after_cleanup,
    )

    with pytest.raises(SourceEvidenceError) as raised:
        source_fetcher._install_verified_cache_candidate(
            cache_root,
            target,
            **_task5a_install_arguments(fixture),
        )

    assert raised.value is primary
    assert primary.__cause__ is prior_cause
    assert primary.__context__ is prior_context
    cleanup_errors = getattr(primary, "cache_cleanup_errors", ())
    assert sum(error is cleanup for error in cleanup_errors) == 1
    assert not os.path.lexists(target)
    assert not any(cache_root.glob(".literature-evidence-staging-*"))


def _task5a_install_directory_close_fault(monkeypatch, cache_root):
    cache_root = Path(os.path.abspath(cache_root))
    real_open = os.open
    real_close = os.close
    real_fstat = os.fstat
    close_error = OSError(errno.EIO, "injected directory close failure")
    state = {
        "root_fd": None,
        "staging_fd": None,
        "close_attempts": [],
        "close_errors": [],
    }

    def recording_open(path, flags, mode=0o777, *, dir_fd=None):
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        rendered = Path(os.fsdecode(path))
        if flags & os.O_DIRECTORY:
            if dir_fd is None and Path(os.path.abspath(rendered)) == cache_root:
                state["root_fd"] = descriptor
            elif (
                dir_fd == state["root_fd"]
                and rendered.name.startswith(".literature-evidence-staging-")
            ):
                state["staging_fd"] = descriptor
        return descriptor

    def faulting_close(descriptor):
        if descriptor == state["staging_fd"]:
            state["close_attempts"].append("staging")
            if not state["close_errors"]:
                state["close_errors"].append(close_error)
                raise close_error
        elif descriptor == state["root_fd"]:
            state["close_attempts"].append("root")
        return real_close(descriptor)

    def reap_injected_descriptors():
        for key in ("staging_fd", "root_fd"):
            descriptor = state[key]
            if descriptor is None:
                continue
            try:
                real_fstat(descriptor)
            except OSError as error:
                if error.errno != errno.EBADF:
                    raise
            else:
                real_close(descriptor)

    monkeypatch.setattr(os, "open", recording_open)
    monkeypatch.setattr(os, "close", faulting_close)
    return state, close_error, reap_injected_descriptors


def test_task5a_prepublication_close_failure_preserves_primary_and_closes_all_fds(
    tmp_path,
    monkeypatch,
):
    fixture = _task5a_lifecycle_fixture()
    cache_root = tmp_path / "source-cache"
    target = cache_root / fixture["source"]["source_id"]
    primary = SourceEvidenceError("injected pre-publication primary")
    prior_cause = RuntimeError("preexisting close-test cause")
    prior_context = RuntimeError("preexisting close-test context")
    primary.__cause__ = prior_cause
    primary.__context__ = prior_context
    real_write = source_fetcher._exclusive_write_bytes

    def fail_primary_write(path, payload):
        if Path(path).name == "source.pdf":
            raise primary
        return real_write(path, payload)

    monkeypatch.setattr(
        source_fetcher,
        "_exclusive_write_bytes",
        fail_primary_write,
    )
    state, close_error, reap = _task5a_install_directory_close_fault(
        monkeypatch,
        cache_root,
    )
    try:
        with pytest.raises(SourceEvidenceError) as raised:
            source_fetcher._install_verified_cache_candidate(
                cache_root,
                target,
                **_task5a_install_arguments(fixture),
            )
    finally:
        reap()

    assert raised.value is primary
    assert primary.__cause__ is prior_cause
    assert primary.__context__ is prior_context
    cleanup_errors = getattr(primary, "cache_cleanup_errors", ())
    assert sum(error is close_error for error in cleanup_errors) == 1
    assert state["close_attempts"] == ["staging", "root"]
    assert not os.path.lexists(target)
    assert not any(cache_root.glob(".literature-evidence-staging-*"))


def test_task5a_postpublication_close_failure_keeps_acquired_outcome(
    tmp_path,
    monkeypatch,
):
    cache_root = tmp_path / "source-cache"
    existing = cache_root / "existing"
    existing.mkdir(parents=True)
    existing.joinpath("sentinel").write_bytes(b"UNCHANGED")
    fixture = _task5a_lifecycle_fixture()
    events = []
    target = cache_root / fixture["source"]["source_id"]
    _task5a_install_real_lifecycle_boundary(
        monkeypatch,
        fixture,
        events=events,
        target=target,
        target_visibility=[],
    )
    state, close_error, reap = _task5a_install_directory_close_fault(
        monkeypatch,
        cache_root,
    )
    try:
        outcome = source_fetcher._fetch_source(
            cache_root,
            fixture["source"],
            fixture["route"],
            ca_bundle=Path("/unused"),
            resume=False,
        )
    finally:
        reap()

    assert state["close_errors"] == [close_error]
    assert state["close_attempts"] == ["staging", "root"]
    assert outcome["status"] == "acquired", outcome
    assert target.is_dir() and not target.is_symlink()
    _task5a_assert_complete_hal_candidate(target, fixture)
    assert {path.name for path in cache_root.iterdir()} == {
        "existing",
        fixture["source"]["source_id"],
    }


def _task5a_crossref_document(doi=TASK5A_GAREL_IDENTITY["value"]):
    return {
        "message": {
            "DOI": doi,
            "title": [TASK5A_GAREL_CROSSREF["title"]],
            "container-title": [TASK5A_GAREL_CROSSREF["venue"]],
            "author": [
                {"given": "T.", "family": "Garel"},
                {"given": "J.-M.", "family": "Maillard"},
            ],
            "published-print": {"date-parts": [[1983, 7, 11]]},
            "volume": "16",
            "issue": "10",
            "page": "2257-2265",
        }
    }


@pytest.mark.parametrize("mutation", ("duplicate-key", "nonfinite"))
def test_task5a_garel_crossref_raw_json_is_strict(mutation, monkeypatch):
    raw = json.dumps(_task5a_crossref_document(), separators=(",", ":")).encode(
        "utf-8"
    )
    if mutation == "duplicate-key":
        doi_field = b'"DOI":"10.1088/0305-4470/16/10/023"'
        raw = raw.replace(doi_field, doi_field + b"," + doi_field, 1)
    else:
        raw = raw[:-1] + b',"review_control":NaN}'

    monkeypatch.setattr(
        source_fetcher,
        "urlopen",
        lambda *args, **kwargs: _FixtureHTTPResponse(
            raw,
            content_type="application/json",
        ),
    )
    with pytest.raises(SourceEvidenceError, match="strict JSON"):
        source_fetcher._crossref_metadata(
            TASK5A_GAREL_IDENTITY["value"],
            object(),
        )


TASK5A_GAREL_RAW_CROSSREF_AUTHORS = (
    {"given": "T.", "family": "Garel"},
    {"given": "J.-M.", "family": "Maillard"},
)


def _task5a_crossref_raw_response(monkeypatch, document):
    raw = json.dumps(
        document,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    monkeypatch.setattr(
        source_fetcher,
        "urlopen",
        lambda *args, **kwargs: _FixtureHTTPResponse(
            raw,
            content_type="application/json",
        ),
    )


@pytest.mark.parametrize(
    "raw_authors",
    (
        pytest.param(
            [*TASK5A_GAREL_RAW_CROSSREF_AUTHORS, {}],
            id="extra-empty-mapping",
        ),
        pytest.param(
            [
                *TASK5A_GAREL_RAW_CROSSREF_AUTHORS,
                {"given": " ", "family": "\t"},
            ],
            id="extra-blank-mapping",
        ),
        pytest.param(
            [TASK5A_GAREL_RAW_CROSSREF_AUTHORS[0]],
            id="missing-author",
        ),
        pytest.param(
            {"first": TASK5A_GAREL_RAW_CROSSREF_AUTHORS[0]},
            id="non-list-container",
        ),
        pytest.param(
            [TASK5A_GAREL_RAW_CROSSREF_AUTHORS[0], "J.-M. Maillard"],
            id="non-mapping-entry",
        ),
        pytest.param(
            [
                TASK5A_GAREL_RAW_CROSSREF_AUTHORS[0],
                {"family": "Maillard"},
            ],
            id="missing-given",
        ),
        pytest.param(
            [
                TASK5A_GAREL_RAW_CROSSREF_AUTHORS[0],
                {"given": "J.-M."},
            ],
            id="missing-family",
        ),
        pytest.param(
            [
                TASK5A_GAREL_RAW_CROSSREF_AUTHORS[0],
                {"given": "  ", "family": "Maillard"},
            ],
            id="blank-given",
        ),
        pytest.param(
            [
                TASK5A_GAREL_RAW_CROSSREF_AUTHORS[0],
                {"given": "J.-M.", "family": "\n"},
            ],
            id="blank-family",
        ),
    ),
)
def test_task5a_garel_crossref_rejects_raw_author_shape_before_filtering(
    monkeypatch,
    raw_authors,
):
    document = _task5a_crossref_document()
    document["message"]["author"] = copy.deepcopy(raw_authors)
    _task5a_crossref_raw_response(monkeypatch, document)

    with pytest.raises(SourceEvidenceError, match="Crossref raw authors"):
        source_fetcher._crossref_metadata(
            TASK5A_GAREL_IDENTITY["value"],
            object(),
        )


def test_task5a_garel_crossref_valid_raw_authors_preserve_exact_order(
    monkeypatch,
):
    document = _task5a_crossref_document()
    assert tuple(document["message"]["author"]) == (
        TASK5A_GAREL_RAW_CROSSREF_AUTHORS
    )
    _task5a_crossref_raw_response(monkeypatch, document)

    assert source_fetcher._crossref_metadata(
        TASK5A_GAREL_IDENTITY["value"],
        object(),
    ) == TASK5A_GAREL_CROSSREF


def test_task5a_other_crossref_route_retains_legacy_filtered_empty_author(
    monkeypatch,
):
    doi = "10.1234/task5a-legacy-filter-control"
    document = _task5a_crossref_document(doi)
    document["message"]["author"].append({})
    _task5a_crossref_raw_response(monkeypatch, document)

    metadata = source_fetcher._crossref_metadata(doi, object())
    assert metadata["authors"] == ["T. Garel", "J.-M. Maillard"]


def test_task5a_other_crossref_route_accepts_valid_json(monkeypatch):
    doi = "10.1234/task5a-generic-control"
    raw = json.dumps(
        _task5a_crossref_document(doi),
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    monkeypatch.setattr(
        source_fetcher,
        "urlopen",
        lambda *args, **kwargs: _FixtureHTTPResponse(
            raw,
            content_type="application/json",
        ),
    )
    metadata = source_fetcher._crossref_metadata(doi, object())
    assert metadata == {
        "title": TASK5A_GAREL_CROSSREF["title"],
        "authors": ["T. Garel", "J.-M. Maillard"],
        "venue": TASK5A_GAREL_CROSSREF["venue"],
        "publication_date": "1983-07-11",
    }


TASK5A_CORE_INITIAL_URL = "https://core.ac.uk/download/572184419.pdf"
TASK5A_CORE_SECOND_URL = (
    "https://fileserver-az.core.ac.uk/download/572184419.pdf"
)
TASK5A_CORE_FINAL_BASE = (
    "https://pdf.core.ac.uk/corefilesystem/pdf/363/572184419.pdf"
)
TASK5A_CORE_SIGNED_QUERY = "download-token=TASK5A_CORE_MEMORY_ONLY_SIGNATURE"


def _task5a_core_url_digest(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _task5a_core_forbidden_query_material():
    token = TASK5A_CORE_SIGNED_QUERY.split("=", 1)[1]
    signed_final = TASK5A_CORE_FINAL_BASE + "?" + TASK5A_CORE_SIGNED_QUERY
    fully_percent_encoded_token = "".join(
        f"%{byte:02X}" for byte in token.encode("ascii")
    )
    return (
        signed_final,
        TASK5A_CORE_SIGNED_QUERY,
        quote_plus(TASK5A_CORE_SIGNED_QUERY, safe=""),
        token,
        fully_percent_encoded_token,
        fully_percent_encoded_token.casefold(),
    )


def test_task5a_core_direct_download_failure_redacts_signed_final_exception(
    tmp_path,
    monkeypatch,
    caplog,
    capsys,
):
    cache_root = tmp_path / "source-cache"
    preexisting = cache_root / "preexisting_source"
    preexisting.mkdir(parents=True)
    preexisting.joinpath("sentinel").write_bytes(b"UNCHANGED")
    before = _task5a_cache_manifest(cache_root)
    route = copy.deepcopy(_core_mg_route())
    route["url"] = TASK5A_CORE_INITIAL_URL
    route["expected_media_type"] = "application/pdf"
    signed_final = TASK5A_CORE_FINAL_BASE + "?" + TASK5A_CORE_SIGNED_QUERY
    opener_requests = []
    validator_receipts = []
    real_validator = source_fetcher.validate_download_response

    class FixtureOpener:
        def __init__(self, redirect_handler):
            self.redirect_handler = redirect_handler

        def open(self, request, timeout):
            opener_requests.append(request.full_url)
            _task5a_complete_core_redirects(
                self.redirect_handler,
                request,
                signed_final,
            )
            return _FixtureHTTPResponse(
                _minimal_pdf("CORE direct signed-final exception fixture."),
                content_type="application/pdf",
                final_url=signed_final,
            )

    def fail_after_real_media_validation(route_spec, **response):
        media_type = real_validator(route_spec, **response)
        assert media_type == "application/pdf"
        validator_receipts.append(response["final_url"])
        raise SourceEvidenceError(
            "CORE media validation failed after signed-final receipt at "
            + response["final_url"]
            + "; signed query "
            + TASK5A_CORE_SIGNED_QUERY
        )

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(
            _task5a_core_handler_from_build_args(handlers)
        ),
    )
    monkeypatch.setattr(
        source_fetcher,
        "validate_download_response",
        fail_after_real_media_validation,
    )

    exposed_exception = None
    try:
        source_fetcher._download(route, object())
    except Exception as error:
        exposed_exception = error
    else:
        pytest.fail("CORE direct signed-final failure was not propagated")

    _task5a_assert_no_forbidden_query_channels(
        forbidden=_task5a_core_forbidden_query_material(),
        exception=exposed_exception,
        caplog=caplog,
        capsys=capsys,
        cache_root=cache_root,
    )
    if opener_requests != [TASK5A_CORE_INITIAL_URL]:
        pytest.fail("CORE direct download used an unexpected initial request")
    if (
        len(validator_receipts) != 1
        or _task5a_core_url_digest(validator_receipts[0])
        != _task5a_core_url_digest(signed_final)
    ):
        pytest.fail("CORE signed final URL did not reach media validation exactly")
    if not isinstance(exposed_exception, SourceEvidenceError):
        pytest.fail("CORE direct download raised the wrong exception type")
    if "CORE media validation failed after signed-final receipt" not in str(
        exposed_exception
    ):
        pytest.fail("CORE direct download failure lost its safe diagnostic")
    assert _task5a_cache_manifest(cache_root) == before


def test_task5a_core_provenance_failure_redacts_signed_final_url_everywhere(
    tmp_path,
    monkeypatch,
    caplog,
    capsys,
):
    cache_root = tmp_path / "source-cache"
    preexisting = cache_root / "preexisting_source"
    preexisting.mkdir(parents=True)
    preexisting.joinpath("sentinel").write_bytes(b"UNCHANGED")
    before = _task5a_cache_manifest(cache_root)
    source_id = "doi_e49cda761520424da334"
    source = {
        "source_id": source_id,
        "canonical_identity": {
            "kind": "doi",
            "value": CORE_MG_BIBLIOGRAPHIC_METADATA["doi"],
        },
        "canonical_url": (
            "https://doi.org/" + CORE_MG_BIBLIOGRAPHIC_METADATA["doi"]
        ),
        "benchmark_names": ["task5a_core_redaction_fixture"],
    }
    authoritative_route = copy.deepcopy(_core_mg_route())
    authoritative_route["url"] = TASK5A_CORE_INITIAL_URL
    authoritative_route["expected_media_type"] = "application/pdf"
    route = {
        "source_id": source_id,
        "authoritative_retrieval_route": authoritative_route,
        "expected_media_type": "application/pdf",
        "access_mode": "unattended",
        "local_cache_location": f"source-cache/{source_id}/source.pdf",
    }
    signed_final = TASK5A_CORE_FINAL_BASE + "?" + TASK5A_CORE_SIGNED_QUERY
    requests = []
    validated_sidecars = []

    class FixtureOpener:
        def __init__(self, redirect_handler):
            self.redirect_handler = redirect_handler

        def open(self, request, timeout):
            requests.append(request.full_url)
            accept = _header_dict(request).get("accept")
            if accept == "application/pdf":
                redirected = _task5a_complete_core_redirects(
                    self.redirect_handler,
                    request,
                    signed_final,
                )
                requests.append(redirected.full_url)
                return _FixtureHTTPResponse(
                    _minimal_pdf("CORE signed final redaction fixture."),
                    content_type="application/pdf",
                    final_url=redirected.full_url,
                )
            assert accept == "application/json"
            return _FixtureHTTPResponse(
                json.dumps(
                    _core_mg_work_identity_document(),
                    separators=(",", ":"),
                ).encode("utf-8"),
                content_type="application/json",
                final_url=authoritative_route["work_identity_evidence"]["url"],
            )

    def validate_exact_sidecar(document, **kwargs):
        assert document == _core_mg_work_identity_document()
        assert kwargs["evidence_kind"] == "core_same_work_output"
        assert kwargs["identity"] == source["canonical_identity"]
        validated_sidecars.append(copy.deepcopy(document))

    def fail_provenance(*args, **kwargs):
        assert validated_sidecars == [_core_mg_work_identity_document()]
        raise SourceEvidenceError(
            "CORE provenance failed after "
            + signed_final
            + "; signing token "
            + TASK5A_CORE_SIGNED_QUERY.split("=", 1)[1]
        )

    monkeypatch.setattr(source_fetcher, "_ssl_context", lambda _path: object())
    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(
            next(
                (
                    handler
                    for handler in handlers
                    if isinstance(
                        handler,
                        source_fetcher._CoreFullTextRedirectHandler,
                    )
                ),
                None,
            )
        ),
    )
    monkeypatch.setattr(
        source_fetcher,
        "_fetch_bibliographic_metadata",
        lambda *args, **kwargs: copy.deepcopy(CORE_MG_BIBLIOGRAPHIC_METADATA),
    )
    monkeypatch.setattr(
        source_fetcher,
        "validate_work_identity_document",
        validate_exact_sidecar,
    )
    monkeypatch.setattr(source_fetcher, "_build_provenance", fail_provenance)

    outcome = source_fetcher._fetch_source(
        cache_root,
        source,
        route,
        ca_bundle=Path("/unused"),
        resume=False,
    )

    _task5a_assert_no_forbidden_query_channels(
        forbidden=_task5a_core_forbidden_query_material(),
        outcome=outcome,
        caplog=caplog,
        capsys=capsys,
        cache_root=cache_root,
    )
    signed_final_digest = _task5a_core_url_digest(signed_final)
    if not any(
        _task5a_core_url_digest(request_url) == signed_final_digest
        for request_url in requests
    ):
        pytest.fail("CORE signed final URL was not used in memory")
    if "CORE provenance failed after" not in outcome["detail"]:
        pytest.fail("CORE provenance failure lost its safe diagnostic")
    assert not os.path.lexists(cache_root / source_id)
    assert not any(path.name.startswith(".") for path in cache_root.iterdir())
    assert _task5a_cache_manifest(cache_root) == before


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


def _task5a_core_handler_from_build_args(handlers):
    matches = [
        handler
        for handler in handlers
        if isinstance(handler, source_fetcher._CoreFullTextRedirectHandler)
    ]
    assert len(matches) == 1
    return matches[0]


def _task5a_complete_core_redirects(handler, initial_request, signed_final):
    assert isinstance(handler, source_fetcher._CoreFullTextRedirectHandler)
    second = _task5a_redirect_request(
        handler,
        initial_request,
        TASK5A_CORE_SECOND_URL,
    )
    return _task5a_redirect_request(handler, second, signed_final)


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

    if second.full_url != TASK5A_CORE_SECOND_URL:
        pytest.fail("CORE first redirect constructed the wrong safe URL")
    if _task5a_core_url_digest(third.full_url) != _task5a_core_url_digest(
        signed_final
    ):
        pytest.fail("CORE final redirect did not retain the signed URL in memory")
    expected_construction_digests = (
        _task5a_core_url_digest(TASK5A_CORE_SECOND_URL),
        _task5a_core_url_digest(signed_final),
    )
    if tuple(map(_task5a_core_url_digest, constructed)) != (
        expected_construction_digests
    ):
        pytest.fail("CORE redirect construction sequence was not exact")
    depth_error = None
    try:
        _task5a_redirect_request(handler, third, signed_final)
    except Exception as error:
        depth_error = error
    if not isinstance(depth_error, SourceEvidenceError):
        pytest.fail("CORE redirect depth was not rejected safely")
    depth_diagnostic = str(depth_error).casefold()
    if not any(word in depth_diagnostic for word in ("redirect", "two", "depth")):
        pytest.fail("CORE redirect-depth rejection lost its safe diagnostic")
    if tuple(map(_task5a_core_url_digest, constructed)) != (
        expected_construction_digests
    ):
        pytest.fail("CORE redirect-depth rejection constructed another request")


TASK5A_CORE_UNSAFE_REDIRECT_CASES = {
    "first-origin": ("first", "https://evil.invalid/download/572184419.pdf"),
    "first-path": (
        "first",
        "https://fileserver-az.core.ac.uk/download/572184418.pdf",
    ),
    "first-userinfo": (
        "first",
        "https://user:password@fileserver-az.core.ac.uk/download/572184419.pdf",
    ),
    "first-query": (
        "first",
        TASK5A_CORE_SECOND_URL + "?too-early=TASK5A_SECRET",
    ),
    "first-fragment": ("first", TASK5A_CORE_SECOND_URL + "#fragment"),
    "final-origin": (
        "final",
        "https://evil.invalid/corefilesystem/pdf/363/572184419.pdf",
    ),
    "final-path": (
        "final",
        "https://pdf.core.ac.uk/corefilesystem/pdf/364/572184419.pdf",
    ),
    "final-userinfo": (
        "final",
        "https://user@pdf.core.ac.uk/corefilesystem/pdf/363/572184419.pdf",
    ),
    "final-fragment": ("final", TASK5A_CORE_FINAL_BASE + "#fragment"),
}


@pytest.mark.parametrize(
    "case_name",
    tuple(TASK5A_CORE_UNSAFE_REDIRECT_CASES),
    ids=tuple(TASK5A_CORE_UNSAFE_REDIRECT_CASES),
)
def test_task5a_core_rejects_unsafe_redirect_before_request_construction_or_issue(
    monkeypatch,
    case_name,
):
    stage, unsafe_url = TASK5A_CORE_UNSAFE_REDIRECT_CASES[case_name]
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
    redirect_error = None
    try:
        _task5a_redirect_request(handler, previous, unsafe_url)
    except Exception as error:
        redirect_error = error
    if not isinstance(redirect_error, SourceEvidenceError):
        pytest.fail("unsafe CORE redirect was not rejected before construction")
    safe_reason_terms = ("core", "redirect", "userinfo", "query", "fragment")
    if not any(
        term in str(redirect_error).casefold() for term in safe_reason_terms
    ):
        pytest.fail("unsafe CORE redirect rejection lost its safe diagnostic")
    if constructed:
        pytest.fail("unsafe CORE redirect reached request construction")


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
    validator_receipts = []
    real_validator = source_fetcher.validate_download_response

    class FixtureOpener:
        def __init__(self, redirect_handler):
            self.redirect_handler = redirect_handler

        def open(self, request, timeout):
            requested.append(request.full_url)
            _task5a_complete_core_redirects(
                self.redirect_handler,
                request,
                signed_final,
            )
            return _FixtureHTTPResponse(
                _minimal_pdf("CORE signed query in-memory control."),
                content_type="application/pdf",
                final_url=signed_final,
            )

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(
            _task5a_core_handler_from_build_args(handlers)
        ),
    )

    def record_validation_receipt(route_spec, **response):
        validator_receipts.append(response["final_url"])
        return real_validator(route_spec, **response)

    monkeypatch.setattr(
        source_fetcher,
        "validate_download_response",
        record_validation_receipt,
    )
    response = source_fetcher._download(route, object())

    assert requested == [TASK5A_CORE_INITIAL_URL]
    assert response["final_url"] == TASK5A_CORE_FINAL_BASE
    if (
        len(validator_receipts) != 1
        or _task5a_core_url_digest(validator_receipts[0])
        != _task5a_core_url_digest(signed_final)
    ):
        pytest.fail("CORE signed final URL did not reach validation in memory")
    serialized_response = json.dumps(response, sort_keys=True)
    if TASK5A_CORE_SIGNED_QUERY in serialized_response:
        pytest.fail("CORE response serialized signed query material")


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


@pytest.mark.parametrize(
    "reflected",
    (
        TASK5A_CORE_SIGNED_QUERY,
        TASK5A_CORE_SIGNED_QUERY.split("=", 1)[1],
        quote_plus(TASK5A_CORE_SIGNED_QUERY, safe=""),
        "".join(
            f"%{byte:02X}"
            for byte in TASK5A_CORE_SIGNED_QUERY.split("=", 1)[1].encode(
                "ascii"
            )
        ),
    ),
    ids=("raw-query", "bare-token", "encoded-component", "encoded-token"),
)
def test_task5a_core_validator_only_query_reflection_is_redacted_everywhere(
    tmp_path,
    monkeypatch,
    caplog,
    capsys,
    reflected,
):
    route = copy.deepcopy(_core_mg_route())
    route["expected_media_type"] = "application/pdf"
    signed_final = TASK5A_CORE_FINAL_BASE + "?" + TASK5A_CORE_SIGNED_QUERY

    class FixtureOpener:
        def __init__(self, redirect_handler):
            self.redirect_handler = redirect_handler

        def open(self, request, timeout):
            _task5a_complete_core_redirects(
                self.redirect_handler,
                request,
                signed_final,
            )
            return _FixtureHTTPResponse(
                _minimal_pdf("CORE validator-only query reflection fixture."),
                content_type="application/pdf",
                final_url=signed_final,
            )

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(
            _task5a_core_handler_from_build_args(handlers)
        ),
    )
    monkeypatch.setattr(
        source_fetcher,
        "validate_download_response",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            SourceEvidenceError("validator reflected only " + reflected)
        ),
    )

    with pytest.raises(SourceEvidenceError) as raised:
        source_fetcher._download(route, object())

    _task5a_assert_no_forbidden_query_channels(
        forbidden=_task5a_core_forbidden_query_material(),
        exception=raised.value,
        caplog=caplog,
        capsys=capsys,
        cache_root=tmp_path,
    )
    assert "validator" in str(raised.value).casefold() or "redact" in str(
        raised.value
    ).casefold()


@pytest.mark.parametrize("completed_hops", (0, 1), ids=("zero-hop", "one-hop"))
def test_task5a_core_download_rejects_incomplete_redirect_sequence_before_body_read(
    monkeypatch,
    completed_hops,
):
    route = copy.deepcopy(_core_mg_route())
    route["expected_media_type"] = "application/pdf"
    final_url = (
        TASK5A_CORE_INITIAL_URL
        if completed_hops == 0
        else TASK5A_CORE_SECOND_URL
    )
    response = _FixtureHTTPResponse(
        _minimal_pdf("CORE incomplete redirect fixture."),
        content_type="application/pdf",
        final_url=final_url,
    )
    body_reads = []
    real_read = response.read

    def tracked_read():
        body_reads.append(True)
        return real_read()

    response.read = tracked_read

    class FixtureOpener:
        def __init__(self, redirect_handler):
            self.redirect_handler = redirect_handler

        def open(self, request, timeout):
            if completed_hops == 1:
                _task5a_redirect_request(
                    self.redirect_handler,
                    request,
                    TASK5A_CORE_SECOND_URL,
                )
            return response

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(
            _task5a_core_handler_from_build_args(handlers)
        ),
    )

    with pytest.raises(SourceEvidenceError, match="CORE|redirect|two|final"):
        source_fetcher._download(route, object())
    assert body_reads == []


@pytest.mark.parametrize(
    "malformed_author",
    (
        "W1 J2 Caspers123",
        "W.@J. Caspers",
        "W.\x00J. Caspers",
        "W J Caspers Jr",
    ),
    ids=("digits", "symbol", "control", "suffix"),
)
def test_task5a_core_crossref_author_parser_rejects_every_unconsumed_character(
    malformed_author,
):
    metadata = copy.deepcopy(CORE_MG_BIBLIOGRAPHIC_METADATA)
    metadata["authors"][0] = malformed_author
    with pytest.raises(SourceEvidenceError, match="author|ambiguous|invalid"):
        validate_work_identity_document(
            _core_mg_work_identity_document(),
            identity={
                "kind": "doi",
                "value": CORE_MG_BIBLIOGRAPHIC_METADATA["doi"],
            },
            authoritative_route=_core_mg_route(),
            evidence_kind="core_same_work_output",
            bibliographic_metadata=metadata,
        )


def _task5a_validate_core_pdf_text(extracted_text):
    return evidence_sources._validate_core_crossref_pdf_agreement(
        _core_mg_work_identity_document(),
        crossref_metadata=CORE_MG_BIBLIOGRAPHIC_METADATA,
        extracted_pdf_text=extracted_text,
        identity={
            "kind": "doi",
            "value": CORE_MG_BIBLIOGRAPHIC_METADATA["doi"],
        },
        authoritative_route=_core_mg_route(),
    )


def test_task5a_core_pdf_title_and_ordered_authors_agree_transitively():
    _task5a_validate_core_pdf_text(CORE_MG_PDF_TEXT)


@pytest.mark.parametrize(
    "mutated_text",
    (
        CORE_MG_PDF_TEXT.replace(
            "The Majumdar-Ghosh chain. Twofold ground state and elementary excitations",
            "The Majumdar-Ghosh chain: Twofold ground state and elementary excitations",
        ),
        CORE_MG_PDF_TEXT.replace(
            "The Majumdar-Ghosh chain. Twofold ground state and elementary excitations",
            "A different spin-chain paper",
        ),
        CORE_MG_PDF_TEXT.replace(" and W Magnus", ""),
        CORE_MG_PDF_TEXT.replace(
            "W J Caspers, K M Emmett and W Magnus",
            "W J Caspers, K M Emmett, A Extra and W Magnus",
        ),
        CORE_MG_PDF_TEXT.replace(
            "W J Caspers, K M Emmett and W Magnus",
            "K M Emmett, W J Caspers and W Magnus",
        ),
        CORE_MG_PDF_TEXT.replace(
            "W J Caspers, K M Emmett and W Magnus",
            "W J Caspers, W J Caspers and W Magnus",
        ),
        CORE_MG_PDF_TEXT.replace("W J Caspers", "J W Caspers"),
        CORE_MG_PDF_TEXT.replace("W J Caspers", "W.@J. Caspers"),
        "Completely different paper by Alice Example and Bob Example.",
    ),
    ids=(
        "api-title-punctuation",
        "wrong-title",
        "missing-author",
        "extra-author",
        "reordered-authors",
        "duplicate-author",
        "wrong-initial-order",
        "ambiguous-author",
        "unrelated-pdf",
    ),
)
def test_task5a_core_pdf_rejects_each_bibliographic_fingerprint_mutation(
    mutated_text,
):
    with pytest.raises(SourceEvidenceError, match="CORE|PDF|title|author"):
        _task5a_validate_core_pdf_text(mutated_text)


def test_task5a_core_offline_replay_rejects_unrelated_structurally_valid_pdf(
    tmp_path,
):
    source_dir, source, route, _descriptor = _special_sidecar_cache(
        tmp_path,
        "core_same_work_output",
    )
    unrelated = _minimal_pdf(
        "Completely different paper by Alice Example and Bob Example."
    )
    source_dir.joinpath("source.pdf").write_bytes(unrelated)
    provenance_path = source_dir / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["raw_payload_sha256"] = hashlib.sha256(unrelated).hexdigest()
    provenance["raw_payload_byte_length"] = len(unrelated)
    provenance["artifact_coordinates"]["end_byte"] = len(unrelated)
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SourceEvidenceError, match="CORE|PDF|title|author"):
        load_verified_source(
            source_dir,
            expected_source=source,
            provisioning_route=route,
        )


@pytest.mark.parametrize(
    ("detail", "expected"),
    (
        (
            "generic retry 17 failed at https://example.invalid/path?retry=1 "
            "after HTTP 401",
            "generic retry 17 failed at https://example.invalid/path after HTTP 401",
        ),
        (
            "source 10.1234/example failed at https://example.invalid/path?id=10",
            "source 10.1234/example failed at https://example.invalid/path",
        ),
    ),
    ids=("one-digit-query", "two-digit-query"),
)
def test_task5a_generic_query_sanitization_preserves_unrelated_numeric_diagnostics(
    detail,
    expected,
):
    assert source_fetcher._sanitize_detail(detail) == expected


TASK5A_OUP_CANONICAL_URL = "https://doi.org/10.1143/ptp/5.2.177"
TASK5A_OUP_IDENTITY_STRING = canonical_source_identity(TASK5A_OUP_CANONICAL_URL)
TASK5A_OUP_IDENTITY_KIND, TASK5A_OUP_IDENTITY_VALUE = (
    TASK5A_OUP_IDENTITY_STRING.split(":", 1)
)
TASK5A_OUP_IDENTITY = {
    "kind": TASK5A_OUP_IDENTITY_KIND,
    "value": TASK5A_OUP_IDENTITY_VALUE,
}
TASK5A_OUP_SOURCE_ID = source_id_for_identity(TASK5A_OUP_IDENTITY_STRING)
TASK5A_OUP_CROSSREF_URL = (
    "https://api.crossref.org/works/10.1143%2Fptp%2F5.2.177"
)
TASK5A_OUP_PRIMARY_RESOURCE_URL = (
    "https://academic.oup.com/ptp/article-lookup/doi/10.1143/ptp/5.2.177"
)


def test_task5a_oup_no_redirect_handler_rejects_redirect_request():
    handler = source_fetcher._OUPNoRedirectHandler()
    request = Request(TASK5A_OUP_CROSSREF_URL)
    with pytest.raises(SourceEvidenceError, match="OUP.*redirect|redirect.*OUP"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            TASK5A_OUP_CROSSREF_URL + "/redirected",
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
    expected_identity = canonical_source_identity(TASK5A_OUP_CANONICAL_URL)
    expected_source_id = source_id_for_identity(expected_identity)
    assert expected_identity == "doi:10.1143/ptp/5.2.177"
    assert expected_source_id == "doi_457c49167653440059e9"
    source_dir, source, route = _write_oup_html_source(tmp_path)
    assert source_dir == tmp_path / expected_source_id
    assert source["source_id"] == route["source_id"] == expected_source_id
    assert source["canonical_identity"] == TASK5A_OUP_IDENTITY
    assert source["canonical_url"] == TASK5A_OUP_CANONICAL_URL
    assert route["local_cache_location"] == (
        f"source-cache/{expected_source_id}/source.html"
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


def _task5a_invalid_oup_crossref_raw(mutation):
    valid_payload = json.dumps(
        _task5a_oup_crossref_document(),
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    if mutation == "trailing-json":
        return (
            valid_payload + b'{"TASK5A_OUP_TRAILING_JSON":true}',
            "TASK5A_OUP_TRAILING_JSON",
        )
    return _round12_invalid_json_sidecar(valid_payload, mutation)


def _task5a_expected_oup_route_spec():
    return {
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


def _task5a_oup_acquisition_fixture():
    route_spec = _task5a_expected_oup_route_spec()
    source = {
        "source_id": TASK5A_OUP_SOURCE_ID,
        "canonical_identity": copy.deepcopy(TASK5A_OUP_IDENTITY),
        "canonical_url": TASK5A_OUP_CANONICAL_URL,
        "benchmark_names": [
            "honeycomb_ising_ferromagnet_exact_tc",
            "triangular_ising_ferromagnet_exact_tc",
        ],
    }
    route = {
        "source_id": TASK5A_OUP_SOURCE_ID,
        "authoritative_retrieval_route": route_spec,
        "expected_media_type": "text/html",
        "access_mode": "unattended",
        "local_cache_location": (
            f"source-cache/{TASK5A_OUP_SOURCE_ID}/source.html"
        ),
    }
    crossref_document = _task5a_oup_crossref_document()
    crossref_raw = json.dumps(
        crossref_document,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    assert evidence_sources._load_json_bytes(
        crossref_raw,
        context="Task 5A OUP Crossref fixture",
    ) == crossref_document
    sidecar_descriptor = {
        "kind": "crossref_oup_same_work",
        "url": TASK5A_OUP_CROSSREF_URL,
        "document_base_url": TASK5A_OUP_CROSSREF_URL,
        "media_type": "application/json",
        "payload_relative_path": "work-identity.json",
        "payload_sha256": hashlib.sha256(crossref_raw).hexdigest(),
        "payload_byte_length": len(crossref_raw),
    }
    return {
        "source": source,
        "route": route,
        "primary_payload": OUP_HTML,
        "crossref_document": crossref_document,
        "crossref_raw": crossref_raw,
        "bibliographic": _task5a_oup_crossref_metadata(),
        "sidecar_descriptor": sidecar_descriptor,
    }


def _task5a_write_oup_snapshot_cache(tmp_path, *, descriptor_mutation=None):
    fixture = _task5a_oup_acquisition_fixture()
    source = fixture["source"]
    route_spec = fixture["route"]["authoritative_retrieval_route"]
    source_dir = tmp_path / source["source_id"]
    provenance = _provenance(fixture["primary_payload"])
    provenance.update(
        {
            "source_id": source["source_id"],
            "source_identity": {
                **source["canonical_identity"],
                "canonical_url": source["canonical_url"],
            },
            "bibliographic_metadata": {
                key: copy.deepcopy(fixture["bibliographic"][key])
                for key in (
                    "title",
                    "authors",
                    "venue",
                    "publication_date",
                )
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
            "authoritative_origin": "publisher",
            "response_headers": {"content-type": "text/html"},
            "immutable_artifact_identifier": route_spec[
                "artifact_identifier"
            ],
            "work_identity_evidence": copy.deepcopy(
                route_spec["work_identity_evidence"]
            ),
        }
    )
    descriptor = copy.deepcopy(fixture["sidecar_descriptor"])
    if descriptor_mutation == "sha256":
        descriptor["payload_sha256"] = "0" * 64
    elif descriptor_mutation == "byte-length":
        descriptor["payload_byte_length"] += 1
    elif descriptor_mutation is not None:
        raise AssertionError(
            f"unknown OUP sidecar descriptor mutation {descriptor_mutation}"
        )
    source_dir.mkdir()
    source_dir.joinpath("source.html").write_bytes(fixture["primary_payload"])
    source_dir.joinpath("provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    source_dir.joinpath("work-identity.json").write_bytes(
        fixture["crossref_raw"]
    )
    source_dir.joinpath("work-identity.provenance.json").write_text(
        json.dumps(descriptor, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return source_dir, fixture


def _task5a_install_oup_memory_opener(
    monkeypatch,
    fixture,
    *,
    crossref_raw=None,
):
    crossref_raw = (
        fixture["crossref_raw"] if crossref_raw is None else crossref_raw
    )
    requests = []
    response_reads = []

    class FixtureResponse(_FixtureHTTPResponse):
        def read(self):
            response_reads.append((self._final_url, self._payload))
            return super().read()

    class FixtureOpener:
        def open(self, request, timeout):
            url = request.full_url
            accept = _header_dict(request).get("accept")
            requests.append((url, accept, timeout))
            if url == TASK5A_OUP_CROSSREF_URL:
                assert "?" not in url
                assert accept == "application/json"
                assert timeout == 30
                return FixtureResponse(
                    crossref_raw,
                    content_type="application/json",
                    final_url=TASK5A_OUP_CROSSREF_URL,
                )
            primary_url = fixture["route"]["authoritative_retrieval_route"][
                "url"
            ]
            assert url == primary_url
            assert "?" not in url
            assert accept == "text/html"
            assert timeout == 60
            return FixtureResponse(
                fixture["primary_payload"],
                content_type="text/html",
                final_url=primary_url,
            )

    monkeypatch.setattr(source_fetcher, "_ssl_context", lambda _path: object())
    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: FixtureOpener(),
    )
    return requests, response_reads


def test_task5a_oup_crossref_redirect_is_rejected_before_second_request_or_body_read(
    monkeypatch,
):
    fixture = _task5a_oup_acquisition_fixture()
    requests = []
    response_reads = []
    selected_handler_names = []

    class RedirectOpener:
        def __init__(self, handlers):
            self.redirect_handler = next(
                handler for handler in handlers if hasattr(handler, "redirect_request")
            )
            selected_handler_names.append(type(self.redirect_handler).__name__)

        def open(self, request, timeout):
            requests.append(request.full_url)
            redirected = self.redirect_handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                TASK5A_OUP_CROSSREF_URL + "/redirected",
            )
            requests.append(redirected.full_url)

            class TrackingResponse(_FixtureHTTPResponse):
                def read(self):
                    response_reads.append(True)
                    return super().read()

            return TrackingResponse(
                fixture["crossref_raw"],
                content_type="application/json",
                final_url=redirected.full_url,
            )

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: RedirectOpener(handlers),
    )

    with pytest.raises(SourceEvidenceError, match="OUP.*redirect|redirect.*OUP"):
        source_fetcher._fetch_work_identity_evidence(
            fixture["source"],
            fixture["route"],
            object(),
            bibliographic_metadata=fixture["bibliographic"],
        )

    assert selected_handler_names == ["_OUPNoRedirectHandler"]
    assert requests == [TASK5A_OUP_CROSSREF_URL]
    assert response_reads == []


@pytest.mark.parametrize(
    "mutation",
    ("source-id", "primary-url", "evidence-url"),
)
def test_task5a_nonexact_oup_crossref_route_is_rejected_before_request(
    monkeypatch,
    mutation,
):
    fixture = _task5a_oup_acquisition_fixture()
    source = copy.deepcopy(fixture["source"])
    route = copy.deepcopy(fixture["route"])
    authoritative_route = route["authoritative_retrieval_route"]
    if mutation == "source-id":
        source["source_id"] = "doi_nonexact_oup_source"
    elif mutation == "primary-url":
        authoritative_route["url"] += "?download=1"
    else:
        authoritative_route["work_identity_evidence"]["url"] += "?mailto=test.invalid"

    opened_urls = []

    class RecordingOpener:
        def open(self, request, timeout):
            opened_urls.append(request.full_url)
            return _FixtureHTTPResponse(
                fixture["crossref_raw"],
                content_type="application/json",
                final_url=request.full_url,
            )

    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *handlers: RecordingOpener(),
    )

    with pytest.raises(SourceEvidenceError, match="OUP.*route|route.*OUP"):
        source_fetcher._fetch_work_identity_evidence(
            source,
            route,
            object(),
            bibliographic_metadata=fixture["bibliographic"],
        )

    assert opened_urls == []


def _task5a_install_snapshot_read_recorder(monkeypatch, cache_root):
    cache_root = Path(os.path.abspath(cache_root))
    real_io_open = io.open
    real_builtin_open = builtins.open
    real_os_open = os.open
    reads = []

    def record(operation, path, *, mode=None, flags=None, dir_fd=None):
        try:
            resolved = _task5a_resolve_open_path(path, dir_fd=dir_fd)
            relative = resolved.relative_to(cache_root)
        except (OSError, TypeError, ValueError):
            return
        if relative.name == "work-identity.json":
            reads.append((operation, resolved, mode, flags))

    def recording_io_open(path, mode="r", *args, **kwargs):
        if "r" in mode and not any(flag in mode for flag in "wax+"):
            record("io.open", path, mode=mode)
        return real_io_open(path, mode, *args, **kwargs)

    def recording_builtin_open(path, mode="r", *args, **kwargs):
        if "r" in mode and not any(flag in mode for flag in "wax+"):
            record("builtins.open", path, mode=mode)
        return real_builtin_open(path, mode, *args, **kwargs)

    def recording_os_open(path, flags, mode=0o777, *, dir_fd=None):
        if flags & os.O_ACCMODE == os.O_RDONLY:
            record(
                "os.open",
                path,
                flags=flags,
                dir_fd=dir_fd,
            )
        return real_os_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(io, "open", recording_io_open)
    monkeypatch.setattr(builtins, "open", recording_builtin_open)
    monkeypatch.setattr(os, "open", recording_os_open)
    return reads, real_io_open


def _task5a_install_cache_write_recorder(monkeypatch, cache_root):
    cache_root = Path(os.path.abspath(cache_root))
    real_io_open = io.open
    real_builtin_open = builtins.open
    real_os_open = os.open
    writes = []

    def record(operation, path, *, mode=None, flags=None, dir_fd=None):
        try:
            resolved = _task5a_resolve_open_path(path, dir_fd=dir_fd)
            relative = resolved.relative_to(cache_root)
        except (OSError, TypeError, ValueError):
            return
        writes.append((operation, relative.as_posix(), mode, flags))

    def recording_io_open(path, mode="r", *args, **kwargs):
        if any(flag in mode for flag in "wax+"):
            record("io.open", path, mode=mode)
        return real_io_open(path, mode, *args, **kwargs)

    def recording_builtin_open(path, mode="r", *args, **kwargs):
        if any(flag in mode for flag in "wax+"):
            record("builtins.open", path, mode=mode)
        return real_builtin_open(path, mode, *args, **kwargs)

    def recording_os_open(path, flags, mode=0o777, *, dir_fd=None):
        if flags & os.O_ACCMODE != os.O_RDONLY or flags & os.O_CREAT:
            record(
                "os.open",
                path,
                flags=flags,
                dir_fd=dir_fd,
            )
        return real_os_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(io, "open", recording_io_open)
    monkeypatch.setattr(builtins, "open", recording_builtin_open)
    monkeypatch.setattr(os, "open", recording_os_open)
    return writes


@pytest.mark.parametrize(
    "mutation",
    (
        "duplicate-key",
        "nan",
        "positive-infinity",
        "negative-infinity",
        "invalid-utf8",
        "malformed-json",
        "trailing-json",
    ),
)
def test_task5a_oup_fetch_source_rejects_strict_crossref_raw_before_primary_or_cache(
    tmp_path,
    monkeypatch,
    mutation,
):
    fixture = _task5a_oup_acquisition_fixture()
    raw, marker = _task5a_invalid_oup_crossref_raw(mutation)
    cache_root = tmp_path / "source-cache"
    requests, response_reads = _task5a_install_oup_memory_opener(
        monkeypatch,
        fixture,
        crossref_raw=raw,
    )
    metadata_calls = []

    def forbidden_separate_metadata(*args, **kwargs):
        metadata_calls.append((args, kwargs))
        raise AssertionError("separate OUP metadata request was attempted")

    monkeypatch.setattr(
        source_fetcher,
        "_fetch_bibliographic_metadata",
        forbidden_separate_metadata,
    )
    cache_writes = _task5a_install_cache_write_recorder(
        monkeypatch,
        cache_root,
    )

    outcome = source_fetcher._fetch_source(
        cache_root,
        fixture["source"],
        fixture["route"],
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert outcome["status"] == "failed", outcome
    assert requests == [
        (TASK5A_OUP_CROSSREF_URL, "application/json", 30)
    ]
    assert response_reads == [(TASK5A_OUP_CROSSREF_URL, raw)]
    assert metadata_calls == []
    assert cache_writes == []
    assert _task5a_cache_manifest(cache_root) == ()
    assert not os.path.lexists(cache_root / TASK5A_OUP_SOURCE_ID)
    rendered = json.dumps(outcome, sort_keys=True)
    assert "strict JSON" in rendered
    assert marker not in rendered
    assert raw.decode("utf-8", errors="ignore") not in rendered


@pytest.mark.parametrize(
    ("descriptor_mutation", "match"),
    (
        ("sha256", "SHA-256"),
        ("byte-length", "byte length"),
    ),
)
def test_task5a_oup_offline_hash_and_length_precede_strict_parse_and_validator(
    tmp_path,
    monkeypatch,
    descriptor_mutation,
    match,
):
    source_dir, fixture = _task5a_write_oup_snapshot_cache(
        tmp_path,
        descriptor_mutation=descriptor_mutation,
    )
    parse_calls = []
    validator_calls = []
    network_calls = []
    real_parser = evidence_sources._load_json_bytes
    real_validator = evidence_sources.validate_work_identity_document

    def recording_parser(payload, *, context):
        if context == "work identity evidence JSON":
            parse_calls.append(payload)
        return real_parser(payload, context=context)

    def recording_validator(document, **kwargs):
        validator_calls.append(document)
        return real_validator(document, **kwargs)

    monkeypatch.setattr(evidence_sources, "_load_json_bytes", recording_parser)
    monkeypatch.setattr(
        evidence_sources,
        "validate_work_identity_document",
        recording_validator,
    )
    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *args, **kwargs: network_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        source_fetcher,
        "urlopen",
        lambda *args, **kwargs: network_calls.append((args, kwargs)),
    )

    with pytest.raises(SourceEvidenceError, match=match):
        load_verified_source(
            source_dir,
            expected_source=fixture["source"],
            provisioning_route=fixture["route"],
        )

    assert parse_calls == []
    assert validator_calls == []
    assert network_calls == []


def test_task5a_oup_offline_replay_reads_one_hashed_snapshot_then_real_validator(
    tmp_path,
    monkeypatch,
):
    source_dir, fixture = _task5a_write_oup_snapshot_cache(tmp_path)
    events = []
    parsed_snapshots = []
    validator_documents = []
    network_calls = []
    sidecar_reads, _real_io_open = _task5a_install_snapshot_read_recorder(
        monkeypatch,
        tmp_path,
    )
    real_parser = evidence_sources._load_json_bytes
    real_validator = evidence_sources.validate_work_identity_document

    def recording_parser(payload, *, context):
        if context == "work identity evidence JSON":
            events.append("strict-parse")
            parsed_snapshots.append(payload)
        return real_parser(payload, context=context)

    def recording_validator(document, **kwargs):
        events.append("real-oup-validator-enter")
        validator_documents.append(document)
        result = real_validator(document, **kwargs)
        events.append("real-oup-validator-complete")
        return result

    monkeypatch.setattr(evidence_sources, "_load_json_bytes", recording_parser)
    monkeypatch.setattr(
        evidence_sources,
        "validate_work_identity_document",
        recording_validator,
    )
    monkeypatch.setattr(
        source_fetcher,
        "build_opener",
        lambda *args, **kwargs: network_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        source_fetcher,
        "urlopen",
        lambda *args, **kwargs: network_calls.append((args, kwargs)),
    )

    verified = load_verified_source(
        source_dir,
        expected_source=fixture["source"],
        provisioning_route=fixture["route"],
    )

    assert verified.source_id == TASK5A_OUP_SOURCE_ID
    assert parsed_snapshots == [fixture["crossref_raw"]]
    assert validator_documents == [fixture["crossref_document"]]
    assert events == [
        "strict-parse",
        "real-oup-validator-enter",
        "real-oup-validator-complete",
    ]
    assert len(sidecar_reads) == 1
    assert sidecar_reads[0][0] in {"io.open", "builtins.open", "os.open"}
    assert sidecar_reads[0][1] == source_dir / "work-identity.json"
    assert network_calls == []


def test_task5a_oup_fetch_source_publishes_one_raw_snapshot_after_real_offline_replay(
    tmp_path,
    monkeypatch,
):
    fixture = _task5a_oup_acquisition_fixture()
    cache_root = tmp_path / "source-cache"
    cache_root.mkdir()
    target = cache_root / TASK5A_OUP_SOURCE_ID
    requests, response_reads = _task5a_install_oup_memory_opener(
        monkeypatch,
        fixture,
    )
    separate_metadata_calls = []
    online_validator_documents = []
    offline_validator_documents = []
    offline_parsed_snapshots = []
    replayed_candidates = []
    events = []
    sidecar_reads, real_io_open = _task5a_install_snapshot_read_recorder(
        monkeypatch,
        cache_root,
    )
    real_online_validator = source_fetcher.validate_work_identity_document
    real_offline_validator = evidence_sources.validate_work_identity_document
    real_offline_parser = evidence_sources._load_json_bytes
    real_loader = source_fetcher.load_verified_source

    def forbidden_separate_metadata(*args, **kwargs):
        separate_metadata_calls.append((args, kwargs))
        raise AssertionError("separate OUP metadata request was attempted")

    def online_validator(document, **kwargs):
        online_validator_documents.append(document)
        return real_online_validator(document, **kwargs)

    def offline_parser(payload, *, context):
        if context == "work identity evidence JSON":
            events.append("offline-strict-parse")
            offline_parsed_snapshots.append(payload)
        return real_offline_parser(payload, context=context)

    def offline_validator(document, **kwargs):
        events.append("offline-real-oup-validator-enter")
        offline_validator_documents.append(document)
        result = real_offline_validator(document, **kwargs)
        events.append("offline-real-oup-validator-complete")
        return result

    def replay_candidate(candidate, **kwargs):
        candidate = Path(candidate)
        events.append("offline-candidate-replay-enter")
        assert candidate != target
        assert candidate.parent == cache_root
        assert candidate.name.startswith(".")
        assert not os.path.lexists(target)
        assert {
            "provenance.json",
            "source.html",
            "work-identity.json",
            "work-identity.provenance.json",
        } <= {path.name for path in candidate.iterdir()}
        verified = real_loader(candidate, **kwargs)
        events.append("offline-candidate-replay-complete")
        replayed_candidates.append(candidate)
        return verified

    monkeypatch.setattr(
        source_fetcher,
        "_fetch_bibliographic_metadata",
        forbidden_separate_metadata,
    )
    monkeypatch.setattr(
        source_fetcher,
        "validate_work_identity_document",
        online_validator,
    )
    monkeypatch.setattr(evidence_sources, "_load_json_bytes", offline_parser)
    monkeypatch.setattr(
        evidence_sources,
        "validate_work_identity_document",
        offline_validator,
    )
    monkeypatch.setattr(source_fetcher, "load_verified_source", replay_candidate)

    outcome = source_fetcher._fetch_source(
        cache_root,
        fixture["source"],
        fixture["route"],
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert outcome["status"] == "acquired", outcome
    assert requests == [
        (TASK5A_OUP_CROSSREF_URL, "application/json", 30),
        (
            fixture["route"]["authoritative_retrieval_route"]["url"],
            "text/html",
            60,
        ),
    ]
    assert response_reads == [
        (TASK5A_OUP_CROSSREF_URL, fixture["crossref_raw"]),
        (
            fixture["route"]["authoritative_retrieval_route"]["url"],
            fixture["primary_payload"],
        ),
    ]
    assert separate_metadata_calls == []
    assert online_validator_documents == [fixture["crossref_document"]]
    assert offline_parsed_snapshots == [fixture["crossref_raw"]]
    assert offline_validator_documents == [fixture["crossref_document"]]
    assert len(replayed_candidates) == 1
    assert events == [
        "offline-candidate-replay-enter",
        "offline-strict-parse",
        "offline-real-oup-validator-enter",
        "offline-real-oup-validator-complete",
        "offline-candidate-replay-complete",
    ]
    assert len(sidecar_reads) == 1
    assert sidecar_reads[0][0] in {"io.open", "builtins.open", "os.open"}
    assert target.is_dir() and not target.is_symlink()
    assert {path.name for path in cache_root.iterdir()} == {
        TASK5A_OUP_SOURCE_ID
    }
    with real_io_open(target / "work-identity.json", "rb") as handle:
        assert handle.read() == fixture["crossref_raw"]
    with real_io_open(
        target / "work-identity.provenance.json",
        "r",
        encoding="utf-8",
    ) as handle:
        assert json.load(handle) == fixture["sidecar_descriptor"]


def test_task5a_oup_offline_candidate_sidecar_failure_leaves_no_target_or_staging(
    tmp_path,
    monkeypatch,
):
    fixture = _task5a_oup_acquisition_fixture()
    cache_root = tmp_path / "source-cache"
    cache_root.mkdir()
    target = cache_root / TASK5A_OUP_SOURCE_ID
    requests, _response_reads = _task5a_install_oup_memory_opener(
        monkeypatch,
        fixture,
    )
    real_loader = source_fetcher.load_verified_source
    parsed_snapshots = []
    real_parser = evidence_sources._load_json_bytes

    def forbidden_separate_metadata(*args, **kwargs):
        raise AssertionError("separate OUP metadata request was attempted")

    def recording_parser(payload, *, context):
        if context == "work identity evidence JSON":
            parsed_snapshots.append(payload)
        return real_parser(payload, context=context)

    def corrupt_then_replay(candidate, **kwargs):
        candidate = Path(candidate)
        assert candidate != target
        assert candidate.parent == cache_root
        descriptor_path = candidate / "work-identity.provenance.json"
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        descriptor["payload_sha256"] = "0" * 64
        descriptor_path.write_text(
            json.dumps(descriptor, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return real_loader(candidate, **kwargs)

    monkeypatch.setattr(
        source_fetcher,
        "_fetch_bibliographic_metadata",
        forbidden_separate_metadata,
    )
    monkeypatch.setattr(evidence_sources, "_load_json_bytes", recording_parser)
    monkeypatch.setattr(
        source_fetcher,
        "load_verified_source",
        corrupt_then_replay,
    )

    outcome = source_fetcher._fetch_source(
        cache_root,
        fixture["source"],
        fixture["route"],
        ca_bundle=Path("/unused"),
        resume=False,
    )

    assert outcome["status"] == "failed", outcome
    assert requests == [
        (TASK5A_OUP_CROSSREF_URL, "application/json", 30),
        (
            fixture["route"]["authoritative_retrieval_route"]["url"],
            "text/html",
            60,
        ),
    ]
    assert "SHA-256" in outcome["detail"]
    assert parsed_snapshots == []
    assert not os.path.lexists(target)
    assert _task5a_cache_manifest(cache_root) == ()


def _task5a_oup_dom_mutation(mutation):
    payload = OUP_HTML
    header_start = payload.index(b'      <header class="article-header">')
    header_end = payload.index(b"</header>", header_start) + len(b"</header>")
    header_subtree = payload[header_start:header_end]
    content_start = payload.index(
        b'      <section class="article-content">', header_end
    )
    content_end = payload.index(b"</section>", content_start) + len(
        b"</section>"
    )
    content_subtree = payload[content_start:content_end]
    citation_start = payload.index(
        b'        <div class="ww-citation-primary">',
        header_start,
    )
    citation_end = payload.index(b"</div>", citation_start) + len(b"</div>")
    citation_subtree = payload[citation_start:citation_end]
    ref_list_start = payload.index(
        b'        <div class="ref-list">',
        content_start,
    )
    ref_list_end = payload.index(b"</div>", ref_list_start) + len(b"</div>")
    ref_list_subtree = payload[ref_list_start:ref_list_end]
    if mutation == "missing-container":
        payload = payload.replace(
            b'class="minimal-article-container"',
            b'class="task5a-container-class-removed"',
            1,
        )
    elif mutation == "duplicate-container":
        payload = payload.replace(
            b"  </body>",
            b'    <article class="minimal-article-container"></article>\n'
            b"  </body>",
            1,
        )
    elif mutation == "missing-header":
        payload = payload.replace(
            header_subtree,
            header_subtree.split(b">", 1)[1].rsplit(b"</header>", 1)[0],
            1,
        )
    elif mutation == "duplicate-header":
        payload = payload.replace(
            header_subtree,
            header_subtree + b'\n      <header class="article-header"></header>',
            1,
        )
    elif mutation == "missing-content":
        payload = payload.replace(
            content_subtree,
            content_subtree.split(b">", 1)[1].rsplit(b"</section>", 1)[0],
            1,
        )
    elif mutation == "duplicate-content":
        payload = payload.replace(
            content_subtree,
            content_subtree
            + b'\n      <section class="article-content"></section>',
            1,
        )
    elif mutation == "header-outside-container":
        payload = payload.replace(header_subtree, b"", 1).replace(
            b"    </article>",
            b"    </article>\n" + header_subtree,
            1,
        )
        assert payload.index(header_subtree) > payload.index(b"    </article>")
    elif mutation == "content-outside-container":
        payload = payload.replace(content_subtree, b"", 1).replace(
            b"    </article>",
            b"    </article>\n" + content_subtree,
            1,
        )
        assert payload.index(content_subtree) > payload.index(b"    </article>")
    elif mutation == "content-before-header":
        separator = payload[header_end:content_start]
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
        payload = payload.replace(citation_subtree, b"", 1).replace(
            b'      <section class="article-content">',
            citation_subtree + b'\n      <section class="article-content">',
            1,
        )
        assert payload.index(b"</header>") < payload.index(citation_subtree)
        assert payload.index(citation_subtree) < payload.index(content_subtree)
    elif mutation == "citation-inside-content":
        payload = payload.replace(citation_subtree, b"", 1).replace(
            b'      <section class="article-content">',
            b'      <section class="article-content">\n' + citation_subtree,
            1,
        )
        assert payload.index(citation_subtree) > payload.index(
            b'      <section class="article-content">'
        )
    elif mutation == "duplicate-citation":
        payload = payload.replace(
            citation_subtree,
            citation_subtree
            + b'\n        <div class="ww-citation-primary"></div>',
            1,
        )
    elif mutation == "missing-citation":
        payload = payload.replace(
            b'class="ww-citation-primary"',
            b'class="task5a-citation-class-removed"',
            1,
        )
    elif mutation == "missing-ref-list":
        payload = payload.replace(
            ref_list_subtree,
            ref_list_subtree.split(b">", 1)[1].rsplit(b"</div>", 1)[0],
            1,
        )
    elif mutation == "duplicate-ref-list":
        payload = payload.replace(
            ref_list_subtree,
            ref_list_subtree + b'\n        <div class="ref-list"></div>',
            1,
        )
    elif mutation == "ref-list-in-header":
        payload = payload.replace(ref_list_subtree, b"", 1).replace(
            b"</header>",
            ref_list_subtree + b"\n      </header>",
            1,
        )
        assert payload.index(ref_list_subtree) < payload.index(b"</header>")
    elif mutation == "ref-list-container-sibling":
        payload = payload.replace(ref_list_subtree, b"", 1).replace(
            b"    </article>",
            ref_list_subtree + b"\n    </article>",
            1,
        )
        assert payload.index(b"</section>") < payload.index(ref_list_subtree)
        assert payload.index(ref_list_subtree) < payload.index(b"    </article>")
    elif mutation == "extra-ref-list-token-outside-body":
        extra_ref_list = (
            b'<aside class="task5a-unrelated ref-list token">'
            b"unrelated navigation</aside>"
        )
        payload = payload.replace(
            b"</html>",
            extra_ref_list + b"\n</html>",
            1,
        )
        assert ref_list_subtree in payload
        assert payload.index(extra_ref_list) > payload.index(b"</body>")
    else:
        raise AssertionError(f"unknown OUP DOM mutation {mutation}")
    assert payload != OUP_HTML
    for unchanged_scientific_anchor in (
        b"The Statistics of Honeycomb and Triangular Lattice. I",
        b"Kodi Husimi",
        b"Itiro Sy&#244;zi",
        OUP_RESOLVER,
        b"Summary",
        b"ch 2H = 2",
        b"exp(4H) = 3",
    ):
        assert unchanged_scientific_anchor in payload
    return payload


def _task5a_oup_dom_carrier_counts(payload):
    class_values = re.findall(
        rb"\bclass\s*=\s*['\"]([^'\"]*)['\"]",
        payload,
        flags=re.IGNORECASE,
    )

    def class_count(class_name):
        return sum(
            class_name in value.decode("ascii").split()
            for value in class_values
        )

    return {
        "class:minimal-article-container": class_count(
            "minimal-article-container"
        ),
        "class:article-header": class_count("article-header"),
        "class:article-content": class_count("article-content"),
        "class:ww-citation-primary": class_count("ww-citation-primary"),
        "class:ref-list": class_count("ref-list"),
        "carrier:title": payload.count(
            b"The Statistics of Honeycomb and Triangular Lattice. I"
        ),
        "carrier:author-husimi": payload.count(b"Kodi Husimi"),
        "carrier:author-syozi": payload.count(b"Itiro Sy&#244;zi"),
        "carrier:canonical-doi": payload.count(OUP_RESOLVER),
        "carrier:cited-doi": payload.count(b"10.1000/cited-work"),
        "carrier:summary": payload.count(b"Summary"),
        "carrier:honeycomb-equation": payload.count(b"ch 2H = 2"),
        "carrier:triangular-equation": payload.count(b"exp(4H) = 3"),
    }


@pytest.mark.parametrize(
    ("mutation", "changed_class", "delta"),
    (
        ("missing-container", "class:minimal-article-container", -1),
        ("duplicate-container", "class:minimal-article-container", 1),
        ("missing-header", "class:article-header", -1),
        ("duplicate-header", "class:article-header", 1),
        ("missing-content", "class:article-content", -1),
        ("duplicate-content", "class:article-content", 1),
        ("missing-citation", "class:ww-citation-primary", -1),
        ("duplicate-citation", "class:ww-citation-primary", 1),
        ("missing-ref-list", "class:ref-list", -1),
        ("duplicate-ref-list", "class:ref-list", 1),
    ),
)
def test_task5a_oup_cardinality_fixtures_change_only_the_intended_class(
    mutation,
    changed_class,
    delta,
):
    base_counts = _task5a_oup_dom_carrier_counts(OUP_HTML)
    mutated_counts = _task5a_oup_dom_carrier_counts(
        _task5a_oup_dom_mutation(mutation)
    )
    changed_counts = {
        name
        for name, base_count in base_counts.items()
        if mutated_counts[name] != base_count
    }
    if changed_counts != {changed_class}:
        pytest.fail("OUP cardinality fixture changed unrelated carriers")
    if mutated_counts[changed_class] != base_counts[changed_class] + delta:
        pytest.fail("OUP cardinality fixture changed the wrong class amount")


def _task5a_oup_exactly_one_class_diagnostic(class_name, actual_count):
    canonical_diagnostic = (
        'OUP DOM cardinality: expected exactly one element with class "'
        f'{class_name}"; found {actual_count}'
    )
    return rf"\A{re.escape(canonical_diagnostic)}\Z"


@pytest.mark.parametrize(
    ("class_name", "actual_count"),
    (
        ("minimal-article-container", 0),
        ("minimal-article-container", 2),
        ("article-header", 0),
        ("article-header", 2),
        ("article-content", 0),
        ("article-content", 2),
        ("ww-citation-primary", 0),
        ("ww-citation-primary", 2),
        ("ref-list", 0),
        ("ref-list", 2),
    ),
)
def test_task5a_oup_class_cardinality_diagnostic_accepts_only_canonical_count(
    class_name,
    actual_count,
):
    canonical_diagnostic = (
        'OUP DOM cardinality: expected exactly one element with class "'
        f'{class_name}"; found {actual_count}'
    )
    pattern = _task5a_oup_exactly_one_class_diagnostic(
        class_name,
        actual_count,
    )
    assert re.search(pattern, canonical_diagnostic) is not None
    assert re.search(pattern, "prefix " + canonical_diagnostic) is None
    assert re.search(pattern, canonical_diagnostic + "; suffix") is None


@pytest.mark.parametrize(
    ("class_name", "unrelated_diagnostic"),
    (
        (
            "minimal-article-container",
            "OUP DOM cardinality: expected exactly one article-header "
            "descendant of minimal-article-container; found 0",
        ),
        (
            "article-header",
            "OUP DOM cardinality: article-header must contain exactly one h1; "
            "found 0",
        ),
        (
            "article-content",
            "OUP DOM cardinality: article-content must contain exactly one "
            "Summary; found 0",
        ),
        (
            "ww-citation-primary",
            "OUP DOM cardinality: ww-citation-primary must contain exactly one "
            "DOI anchor; found 0",
        ),
        (
            "ref-list",
            "OUP DOM cardinality: ref-list must contain exactly one citation; "
            "found 0",
        ),
    ),
)
def test_task5a_oup_class_cardinality_diagnostic_rejects_descendant_counts(
    class_name,
    unrelated_diagnostic,
):
    assert re.search(
        _task5a_oup_exactly_one_class_diagnostic(class_name, 0),
        unrelated_diagnostic,
    ) is None


@pytest.mark.parametrize(
    ("mutation", "class_name", "actual_count"),
    (
        ("missing-container", "minimal-article-container", 0),
        ("duplicate-container", "minimal-article-container", 2),
        ("missing-header", "article-header", 0),
        ("duplicate-header", "article-header", 2),
        ("missing-content", "article-content", 0),
        ("duplicate-content", "article-content", 2),
        ("missing-citation", "ww-citation-primary", 0),
        ("duplicate-citation", "ww-citation-primary", 2),
        ("missing-ref-list", "ref-list", 0),
        ("duplicate-ref-list", "ref-list", 2),
    ),
)
def test_task5a_oup_rejects_each_dom_cardinality_mutation_with_exact_diagnostic(
    mutation,
    class_name,
    actual_count,
):
    with pytest.raises(
        SourceEvidenceError,
        match=_task5a_oup_exactly_one_class_diagnostic(
            class_name,
            actual_count,
        ),
    ):
        _validate_oup_html_payload(_task5a_oup_dom_mutation(mutation))


@pytest.mark.parametrize(
    "mutation",
    (
        "header-outside-container",
        "content-outside-container",
        "content-before-header",
        "citation-outside-header",
        "citation-inside-content",
        "ref-list-in-header",
        "ref-list-container-sibling",
        "extra-ref-list-token-outside-body",
    ),
)
def test_task5a_oup_rejects_each_dom_hierarchy_mutation(
    mutation,
):
    with pytest.raises(SourceEvidenceError):
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
        payload = payload.replace(exact_anchor, b"", 1)
        assert payload.count(b'class="ww-citation-primary"') == 1
        assert b'<div class="ww-citation-primary">' in payload
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


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
def test_task5a_oup_rejects_header_byline_with_third_author(
    tmp_path,
    validation_mode,
):
    exact_byline = (
        b'<p class="authors">Kodi Husimi and Itiro Sy&#244;zi</p>'
    )
    payload = OUP_HTML.replace(
        exact_byline,
        b'<p class="authors">Kodi Husimi and Itiro Sy&#244;zi and Ada Example</p>',
        1,
    )
    assert OUP_HTML.count(exact_byline) == 1
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="author"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


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


@pytest.mark.parametrize("validation_mode", ("download", "offline"))
def test_task5a_oup_rejects_title_and_extra_doi_outside_container(
    tmp_path,
    validation_mode,
):
    outside_carrier = (
        b"    <p>The Statistics of Honeycomb and Triangular Lattice. I "
        b"10.9999/extra</p>\n"
    )
    payload = OUP_HTML.replace(
        b"  </body>",
        outside_carrier + b"  </body>",
        1,
    )
    assert outside_carrier in payload
    assert payload != OUP_HTML
    with pytest.raises(SourceEvidenceError, match="DOI|carrier|container"):
        _validate_oup_html_payload_in_mode(payload, validation_mode, tmp_path)


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
    with pytest.raises(SourceEvidenceError, match="DOI|carrier|ref-list"):
        _validate_oup_html_payload(_task5a_oup_css_v2_payload(stylesheet))


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
    with pytest.raises(SourceEvidenceError, match="DOI|carrier|ref-list"):
        _validate_oup_html_payload(_task5a_oup_css_v2_payload(stylesheet))


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
