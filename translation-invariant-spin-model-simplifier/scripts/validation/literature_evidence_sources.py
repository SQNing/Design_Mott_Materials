"""Offline verification for authoritative literature source payloads."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess
from types import MappingProxyType
from urllib.parse import urlparse
import xml.etree.ElementTree as ElementTree

from validation.literature_evidence_schema import (
    EvidenceSchemaError,
    SourceProvenance,
)


_PROVENANCE_FIELDS = {
    "schema_version",
    "source_id",
    "source_identity",
    "bibliographic_metadata",
    "retrieval_metadata",
    "media_type",
    "raw_payload_sha256",
    "raw_payload_byte_length",
    "payload_relative_path",
    "artifact_coordinates",
    "license_access_notes",
    "citation_metadata_verification",
    "text_extraction",
}
_AUTHORITATIVE_ORIGINS = {
    "publisher",
    "arxiv",
    "institutional_repository",
    "author_repository",
}
_OPEN_REPOSITORY_ROUTES = {
    "10.1016/j.aop.2005.10.005": ("cond-mat/0506438", "W2141708961"),
    "10.1016/s0003-4916(02)00018-0": ("quant-ph/9707021", "W2135273380"),
    "10.1038/nmat1867": ("cond-mat/0702589", "W1968777969"),
    "10.1038/nphys3826": ("1606.06463", "W2463289911"),
    "10.1088/0305-4470/38/26/003": ("cond-mat/0502556", "W1975695579"),
    "10.1088/1361-648x/aa8cf5": ("1706.06113", "W2631568866"),
    "10.1126/science.1064761": ("cond-mat/0201427", "W2128117725"),
    "10.1126/science.1201080": ("1011.6114", "W2057666228"),
    "10.1126/science.271.5249.618": ("cond-mat/9509181", "W2055891591"),
    "10.1143/jpsj.70.3377": ("cond-mat/0111127", "W2131097405"),
    "10.1143/jpsj.78.043704": ("0902.3028", "W2091151398"),
    "10.1007/s10955-017-1946-0": ("1708.05186", "W2745733334"),
}
_INSTITUTIONAL_REPOSITORY_ROUTES = {}
_OPEN_PUBLISHER_ROUTES = {
    "10.1038/ncomms14113": ("ncomms14113", "W2591608240"),
    "10.1038/ncomms2914": ("ncomms2914", "W2068740639"),
    "10.1038/ncomms3287": ("ncomms3287", "W2103622306"),
    "10.1038/ncomms5203": ("ncomms5203", "W2013284845"),
    "10.1038/ncomms6137": ("ncomms6137", "W1695352508"),
    "10.1038/srep16419": ("srep16419", "W3105052732"),
}


def authoritative_origin_for_route_kind(route_kind):
    """Return the provenance origin implied by an acquisition route."""

    return {
        "arxiv_export_pdf": "arxiv",
        "arxiv_author_manuscript_pdf": "author_repository",
        "institutional_repository_pdf": "institutional_repository",
    }.get(route_kind, "publisher")


def authoritative_route_for_identity(identity):
    """Return the publisher-specific authoritative acquisition route."""

    _require_mapping(identity, "canonical source identity")
    if set(identity) != {"kind", "value"}:
        raise SourceEvidenceError("canonical source identity must contain kind and value")
    kind = identity["kind"]
    value = identity["value"]
    _require_text(kind, "source identity kind")
    _require_text(value, "source identity value")
    def canonical_route(route_kind, url, media_type, access_mode):
        canonical_url = (
            f"https://arxiv.org/abs/{value}"
            if kind == "arxiv"
            else f"https://doi.org/{value}"
        )
        return _route(
            route_kind,
            url,
            media_type,
            access_mode,
            artifact_identifier=f"{kind}:{value}",
            work_identity_evidence={
                "kind": "canonical_identity",
                "url": canonical_url,
            },
        )

    if kind == "arxiv":
        return canonical_route(
            "arxiv_export_pdf",
            f"https://export.arxiv.org/pdf/{value}",
            "application/pdf",
            "unattended",
        )
    if kind != "doi":
        raise SourceEvidenceError(f"unsupported canonical source identity kind {kind}")
    prefix, separator, suffix = value.partition("/")
    if not separator:
        raise SourceEvidenceError("DOI identity must contain a registrant prefix and suffix")
    repository_route = _OPEN_REPOSITORY_ROUTES.get(value.lower())
    if repository_route is not None:
        arxiv_id, openalex_id = repository_route
        return _route(
            "arxiv_author_manuscript_pdf",
            f"https://export.arxiv.org/pdf/{arxiv_id}",
            "application/pdf",
            "unattended",
            artifact_identifier=f"arxiv:{arxiv_id}",
            work_identity_evidence={
                "kind": "openalex_same_work_location",
                "url": f"https://api.openalex.org/works/{openalex_id}",
            },
        )
    publisher_route = _OPEN_PUBLISHER_ROUTES.get(value.lower())
    if publisher_route is not None:
        article_id, openalex_id = publisher_route
        return _route(
            "nature_open_article_pdf",
            f"https://www.nature.com/articles/{article_id}.pdf",
            "application/pdf",
            "unattended",
            artifact_identifier=f"doi:{value}",
            work_identity_evidence={
                "kind": "openalex_publisher_oa_location",
                "url": f"https://api.openalex.org/works/{openalex_id}",
            },
        )
    institutional_route = _INSTITUTIONAL_REPOSITORY_ROUTES.get(value.lower())
    if institutional_route is not None:
        return _route(
            "institutional_repository_pdf",
            institutional_route["url"],
            "application/pdf",
            "unattended",
            artifact_identifier=institutional_route["artifact_identifier"],
            work_identity_evidence={
                "kind": "semantic_scholar_same_work_location",
                "url": (
                    "https://api.semanticscholar.org/graph/v1/paper/"
                    + institutional_route["semantic_scholar_id"]
                    + "?fields=paperId,title,externalIds,openAccessPdf,url"
                ),
            },
        )
    if prefix == "10.1103":
        return canonical_route(
            "aps_harvest_pdf",
            f"https://harvest.aps.org/v2/journals/articles/{value}/fulltext",
            "application/pdf",
            "unattended",
        )
    if prefix == "10.1016":
        return canonical_route(
            "elsevier_article_api_xml",
            f"https://api.elsevier.com/content/article/doi/{value}",
            "application/xml",
            "api_key_or_entitlement",
        )
    if prefix == "10.1038":
        return canonical_route(
            "nature_article_pdf",
            f"https://www.nature.com/articles/{suffix}.pdf",
            "application/pdf",
            "authenticated_session",
        )
    if prefix == "10.1007":
        return canonical_route(
            "springer_content_pdf",
            f"https://link.springer.com/content/pdf/{value}.pdf",
            "application/pdf",
            "authenticated_session",
        )
    if prefix == "10.1140":
        return canonical_route(
            "epj_springer_content_pdf",
            f"https://link.springer.com/content/pdf/{value}.pdf",
            "application/pdf",
            "authenticated_session",
        )
    if prefix == "10.1088":
        return canonical_route(
            "iop_article_pdf",
            f"https://iopscience.iop.org/article/{value}/pdf",
            "application/pdf",
            "challenge_or_institutional",
        )
    if prefix == "10.1209":
        return canonical_route(
            "epl_iop_article_pdf",
            f"https://iopscience.iop.org/article/{value}/pdf",
            "application/pdf",
            "challenge_or_institutional",
        )
    if prefix == "10.1126":
        return canonical_route(
            "science_article_pdf",
            f"https://www.science.org/doi/pdf/{value}",
            "application/pdf",
            "challenge_or_institutional",
        )
    if prefix == "10.1063":
        return canonical_route(
            "aip_article_discovery",
            f"https://doi.org/{value}",
            "application/pdf",
            "challenge_or_institutional",
        )
    if prefix == "10.1021":
        return canonical_route(
            "acs_article_pdf",
            f"https://pubs.acs.org/doi/pdf/{value}",
            "application/pdf",
            "challenge_or_institutional",
        )
    if prefix == "10.1143":
        return canonical_route(
            "jpsj_article_pdf",
            f"https://journals.jps.jp/doi/pdf/{value}",
            "application/pdf",
            "challenge_or_institutional",
        )
    if prefix == "10.1002":
        return canonical_route(
            "wiley_book_provisioning",
            f"https://doi.org/{value}",
            "application/pdf",
            "licensed_manual_provisioning",
        )
    raise SourceEvidenceError(f"no authoritative route is declared for DOI prefix {prefix}")


def _route(
    kind,
    url,
    media_type,
    access_mode,
    *,
    artifact_identifier,
    work_identity_evidence,
):
    return {
        "kind": kind,
        "url": url,
        "expected_media_type": media_type,
        "access_mode": access_mode,
        "artifact_identifier": artifact_identifier,
        "work_identity_evidence": work_identity_evidence,
    }


def arxiv_atom_identifier_matches(atom_identifier, canonical_id):
    """Match an Atom entry ID to the same arXiv work, ignoring only vN."""

    if not isinstance(atom_identifier, str) or not isinstance(canonical_id, str):
        return False
    path = urlparse(atom_identifier).path.strip("/")
    if path.lower().startswith("abs/"):
        path = path[4:]
    base_id = re.sub(r"v\d+$", "", path, flags=re.IGNORECASE)
    return base_id.casefold() == canonical_id.strip().casefold()


def validate_download_response(route, *, status, headers, body, final_url):
    """Validate response bytes before they can enter the local source cache."""

    _require_mapping(route, "authoritative route")
    _require_mapping(headers, "response headers")
    if status != 200:
        raise SourceEvidenceError(f"authoritative download returned HTTP status {status}")
    if not isinstance(body, bytes) or not body:
        raise SourceEvidenceError("authoritative download returned an empty body")
    final_host = urlparse(final_url).hostname or ""
    blocked_hosts = {
        "validate.perfdrive.com",
        "idp.nature.com",
        "challenges.cloudflare.com",
    }
    if final_host.lower() in blocked_hosts:
        raise SourceEvidenceError(f"authoritative download ended at challenge host {final_host}")
    normalized_headers = {str(key).lower(): str(value) for key, value in headers.items()}
    content_type = normalized_headers.get("content-type", "").split(";", 1)[0].strip().lower()
    expected = route.get("expected_media_type")
    if content_type != expected:
        raise SourceEvidenceError(
            f"download media type {content_type or 'missing'} does not match {expected}"
        )
    if expected == "application/pdf":
        if not body.startswith(b"%PDF-"):
            raise SourceEvidenceError("download body does not have a PDF signature")
        if len(body) < 512 or b"%%EOF" not in body[-1024:]:
            raise SourceEvidenceError("downloaded PDF is truncated or implausibly short")
    elif expected == "application/xml":
        lowered = body.lower()
        if b"unauthorized request results in minimized metadata" in lowered:
            raise SourceEvidenceError("Elsevier response is minimized metadata, not full text")
        _xml_article_text(body, context="downloaded XML")
    else:
        raise SourceEvidenceError(f"unsupported authoritative media type {expected}")
    return content_type


class SourceEvidenceError(ValueError):
    """Raised when a local source payload cannot prove its provenance."""


@dataclass(frozen=True)
class VerifiedSource:
    source_id: str
    provenance: SourceProvenance
    payload_path: Path
    payload_bytes: bytes
    payload_sha256: str
    extracted_text: str
    extraction_tool: Mapping

    def __post_init__(self):
        object.__setattr__(
            self, "extraction_tool", MappingProxyType(dict(self.extraction_tool))
        )


def load_verified_source(
    source_dir,
    *,
    expected_source,
    provisioning_route,
    required_search_anchors=(),
):
    """Load and verify one source directory without performing network access."""

    root = Path(source_dir)
    raw = _load_json(root / "provenance.json")
    _require_exact_fields(raw, _PROVENANCE_FIELDS, "provenance")
    if raw["schema_version"] != 1:
        raise SourceEvidenceError("unsupported provenance schema_version")
    _validate_expected_source(raw, expected_source, provisioning_route)
    _validate_bibliographic_metadata(raw["bibliographic_metadata"])
    _validate_retrieval_metadata(raw["retrieval_metadata"], raw["source_identity"], provisioning_route)
    _validate_work_identity_payload(
        root,
        raw["retrieval_metadata"],
        raw["source_identity"],
        provisioning_route,
    )
    _validate_structured_notes(raw)

    payload_path = _payload_path(root, raw["payload_relative_path"])
    try:
        payload = payload_path.read_bytes()
    except OSError as exc:
        raise SourceEvidenceError(f"cannot read source payload {payload_path}: {exc}") from exc
    if not payload:
        raise SourceEvidenceError("empty payload cannot establish source evidence")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != raw["raw_payload_sha256"]:
        raise SourceEvidenceError("payload SHA-256 does not match provenance")
    if len(payload) != raw["raw_payload_byte_length"]:
        raise SourceEvidenceError("payload byte length does not match provenance")
    _validate_coordinates(raw["artifact_coordinates"], len(payload))

    media_type = raw["media_type"]
    if media_type != provisioning_route.get("expected_media_type"):
        raise SourceEvidenceError("payload media type disagrees with provisioning route")
    extracted_text = _extract_text(
        payload_path, payload, media_type, raw["text_extraction"]
    )
    _require_target_anchors(extracted_text, required_search_anchors)

    provenance_fields = {
        key: raw[key]
        for key in (
            "source_id",
            "source_identity",
            "bibliographic_metadata",
            "retrieval_metadata",
            "media_type",
            "raw_payload_sha256",
            "raw_payload_byte_length",
            "license_access_notes",
            "citation_metadata_verification",
        )
    }
    try:
        provenance = SourceProvenance(**provenance_fields)
    except EvidenceSchemaError as exc:
        raise SourceEvidenceError(f"invalid source provenance schema: {exc}") from exc
    return VerifiedSource(
        source_id=raw["source_id"],
        provenance=provenance,
        payload_path=payload_path,
        payload_bytes=payload,
        payload_sha256=digest,
        extracted_text=extracted_text,
        extraction_tool=raw["text_extraction"],
    )


def _validate_expected_source(raw, expected_source, provisioning_route):
    _require_mapping(expected_source, "expected source")
    _require_mapping(provisioning_route, "provisioning route")
    source_id = expected_source.get("source_id")
    if raw["source_id"] != source_id or provisioning_route.get("source_id") != source_id:
        raise SourceEvidenceError("source identity disagrees with source index or provisioning")
    expected_identity = expected_source.get("canonical_identity")
    expected_url = expected_source.get("canonical_url")
    identity = raw["source_identity"]
    _require_exact_fields(
        identity, {"kind", "value", "canonical_url"}, "source_identity"
    )
    if (
        identity.get("kind") != expected_identity.get("kind")
        or identity.get("value") != expected_identity.get("value")
        or identity.get("canonical_url") != expected_url
    ):
        raise SourceEvidenceError("source identity disagrees with canonical source index")


def _validate_bibliographic_metadata(metadata):
    required = {"title", "authors", "venue", "publication_date"}
    _require_exact_fields(metadata, required, "bibliographic_metadata")
    for field in ("title", "venue"):
        _require_text(metadata[field], field)
    authors = metadata["authors"]
    if (
        not isinstance(authors, Sequence)
        or isinstance(authors, (str, bytes, bytearray))
        or not authors
        or any(not isinstance(author, str) or not author.strip() for author in authors)
    ):
        raise SourceEvidenceError("authors must be a nonempty list of names")
    try:
        date.fromisoformat(metadata["publication_date"])
    except (TypeError, ValueError) as exc:
        raise SourceEvidenceError("publication_date must be an ISO date") from exc


def _validate_retrieval_metadata(metadata, identity, provisioning_route):
    required = {
        "url",
        "retrieved_at",
        "method",
        "authoritative_origin",
        "http_status",
        "response_headers",
        "immutable_artifact_identifier",
    }
    _require_mapping(metadata, "retrieval_metadata")
    missing = sorted(required - set(metadata))
    extra = sorted(set(metadata) - required - {"work_identity_evidence"})
    if missing:
        raise SourceEvidenceError(
            f"retrieval_metadata missing required field {missing[0]}"
        )
    if extra:
        raise SourceEvidenceError(
            f"retrieval_metadata contains unsupported field {extra[0]}"
        )
    _require_text(metadata["url"], "url")
    try:
        datetime.fromisoformat(metadata["retrieved_at"])
    except (TypeError, ValueError) as exc:
        raise SourceEvidenceError("retrieved_at must be an ISO timestamp") from exc
    expected_method = provisioning_route.get("authoritative_retrieval_route", {}).get(
        "kind"
    )
    if metadata["method"] != expected_method:
        raise SourceEvidenceError("authoritative retrieval method disagrees with provisioning")
    if metadata["authoritative_origin"] not in _AUTHORITATIVE_ORIGINS:
        raise SourceEvidenceError("authoritative retrieval origin is invalid")
    expected_origin = authoritative_origin_for_route_kind(expected_method)
    if metadata["authoritative_origin"] != expected_origin:
        raise SourceEvidenceError(
            "authoritative retrieval origin disagrees with provisioning route"
        )
    status = metadata["http_status"]
    if isinstance(status, bool) or not isinstance(status, int) or not 200 <= status < 300:
        raise SourceEvidenceError("http_status must be a successful integer status")
    _require_mapping(metadata["response_headers"], "response_headers")
    route = provisioning_route.get("authoritative_retrieval_route", {})
    expected_artifact_id = route.get(
        "artifact_identifier", f"{identity['kind']}:{identity['value']}"
    )
    if metadata["immutable_artifact_identifier"] != expected_artifact_id:
        raise SourceEvidenceError("immutable_artifact_identifier disagrees with source identity")
    evidence = route.get("work_identity_evidence")
    if evidence and evidence.get("kind") != "canonical_identity":
        stored = metadata.get("work_identity_evidence")
        _require_mapping(stored, "work_identity_evidence")
        if not _same_work_identity_route(stored, evidence):
            raise SourceEvidenceError("work identity evidence route disagrees with provisioning")
        allowed = {
            "kind",
            "url",
            "payload_relative_path",
            "payload_sha256",
            "payload_byte_length",
        }
        if set(stored) not in ({"kind", "url"}, allowed):
            raise SourceEvidenceError("work_identity_evidence has invalid fields")
    elif "work_identity_evidence" in metadata:
        raise SourceEvidenceError("canonical publisher route must not add work identity evidence")


def _same_work_identity_route(stored, expected):
    if stored.get("kind") != expected.get("kind"):
        return False
    stored_url = stored.get("url")
    expected_url = expected.get("url")
    if stored_url == expected_url:
        return True
    if not isinstance(stored_url, str) or not isinstance(expected_url, str):
        return False
    left = urlparse(stored_url)
    right = urlparse(expected_url)
    kind = expected["kind"]
    if kind.startswith("openalex_"):
        allowed_hosts = {"openalex.org", "api.openalex.org"}
        left_id = left.path.rstrip("/").rsplit("/", 1)[-1]
        right_id = right.path.rstrip("/").rsplit("/", 1)[-1]
        return (
            left.hostname in allowed_hosts
            and right.hostname in allowed_hosts
            and re.fullmatch(r"W\d+", left_id) is not None
            and left_id == right_id
        )
    if kind == "semantic_scholar_same_work_location":
        return (
            left.hostname == right.hostname == "api.semanticscholar.org"
            and left.path.rstrip("/") == right.path.rstrip("/")
        )
    return False


def _validate_work_identity_payload(root, metadata, identity, provisioning_route):
    route = provisioning_route.get("authoritative_retrieval_route", {})
    expected = route.get("work_identity_evidence", {})
    if expected.get("kind") in {None, "canonical_identity"}:
        return
    stored = metadata["work_identity_evidence"]
    if "payload_relative_path" in stored:
        descriptor = stored
    else:
        descriptor = _load_json(root / "work-identity.provenance.json")
        _require_exact_fields(
            descriptor,
            {
                "kind",
                "url",
                "payload_relative_path",
                "payload_sha256",
                "payload_byte_length",
            },
            "work identity sidecar provenance",
        )
        if not _same_work_identity_route(descriptor, stored):
            raise SourceEvidenceError("work identity sidecar disagrees with source provenance")
    evidence_path = _payload_path(root, descriptor["payload_relative_path"])
    try:
        payload = evidence_path.read_bytes()
    except OSError as exc:
        raise SourceEvidenceError(
            f"cannot read work identity evidence {evidence_path}: {exc}"
        ) from exc
    if not payload:
        raise SourceEvidenceError("work identity evidence payload is empty")
    if hashlib.sha256(payload).hexdigest() != descriptor["payload_sha256"]:
        raise SourceEvidenceError("work identity evidence SHA-256 does not match provenance")
    if len(payload) != descriptor["payload_byte_length"]:
        raise SourceEvidenceError("work identity evidence byte length does not match provenance")
    document = _load_json(evidence_path)
    validate_work_identity_document(
        document,
        identity=identity,
        authoritative_route=route,
        evidence_kind=descriptor["kind"],
    )


def validate_work_identity_document(
    document,
    *,
    identity,
    authoritative_route,
    evidence_kind,
):
    """Prove that an external work record links a DOI to the retrieved artifact."""

    _require_mapping(document, "work identity evidence document")
    canonical_doi = identity.get("value", "").casefold()
    artifact_identifier = authoritative_route.get("artifact_identifier", "")
    if evidence_kind.startswith("openalex_"):
        reported_doi = str(document.get("doi", ""))
        if reported_doi.casefold() != f"https://doi.org/{canonical_doi}":
            raise SourceEvidenceError("work identity evidence canonical DOI mismatch")
        locations = document.get("locations")
        if not isinstance(locations, list):
            raise SourceEvidenceError("OpenAlex work identity evidence has no locations")
        location_urls = {
            location.get(field)
            for location in locations
            if isinstance(location, Mapping)
            for field in ("pdf_url", "landing_page_url")
            if isinstance(location.get(field), str)
        }
    elif evidence_kind == "semantic_scholar_same_work_location":
        external_ids = document.get("externalIds")
        if not isinstance(external_ids, Mapping) or str(
            external_ids.get("DOI", "")
        ).casefold() != canonical_doi:
            raise SourceEvidenceError("work identity evidence canonical DOI mismatch")
        open_pdf = document.get("openAccessPdf")
        location_urls = {
            open_pdf.get("url")
        } if isinstance(open_pdf, Mapping) and isinstance(open_pdf.get("url"), str) else set()
    else:
        raise SourceEvidenceError(
            f"unsupported work identity evidence kind {evidence_kind}"
        )
    if not _artifact_location_matches(
        artifact_identifier,
        authoritative_route.get("url", ""),
        location_urls,
    ):
        raise SourceEvidenceError("work identity evidence does not locate the retrieved artifact")


def _artifact_location_matches(artifact_identifier, retrieval_url, location_urls):
    if artifact_identifier.startswith("arxiv:"):
        expected_id = artifact_identifier.split(":", 1)[1]
        for location_url in location_urls:
            parsed = urlparse(location_url)
            if parsed.hostname not in {"arxiv.org", "export.arxiv.org"}:
                continue
            path = parsed.path.strip("/")
            for prefix in ("pdf/", "abs/"):
                if path.startswith(prefix):
                    path = path[len(prefix) :]
            path = path.removesuffix(".pdf")
            if arxiv_atom_identifier_matches(
                f"https://arxiv.org/abs/{path}", expected_id
            ):
                return True
        return False
    return retrieval_url in location_urls


def _validate_structured_notes(raw):
    license_notes = raw["license_access_notes"]
    _require_exact_fields(
        license_notes,
        {"access_status", "redistributability", "notes"},
        "license_access_notes",
    )
    for field in ("access_status", "redistributability", "notes"):
        _require_text(license_notes[field], field)
    verification = raw["citation_metadata_verification"]
    _require_exact_fields(
        verification,
        {"status", "verified_fields"},
        "citation_metadata_verification",
    )
    if verification["status"] != "verified":
        raise SourceEvidenceError("citation metadata must be verified")
    fields = verification["verified_fields"]
    if (
        not isinstance(fields, Sequence)
        or isinstance(fields, (str, bytes, bytearray))
        or not fields
    ):
        raise SourceEvidenceError("verified_fields must be nonempty")


def _payload_path(root, relative_path):
    _require_text(relative_path, "payload_relative_path")
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or len(pure.parts) != 1 or pure.parts[0] in {".", ".."}:
        raise SourceEvidenceError("payload_relative_path must name one local payload file")
    return root / pure.name


def _validate_coordinates(coordinates, payload_length):
    _require_exact_fields(
        coordinates,
        {"kind", "start_byte", "end_byte"},
        "artifact_coordinates",
    )
    if coordinates["kind"] != "whole_payload":
        raise SourceEvidenceError("artifact coordinates must describe whole_payload")
    if coordinates["start_byte"] != 0 or coordinates["end_byte"] != payload_length:
        raise SourceEvidenceError("artifact coordinates do not cover exact payload bytes")


def _extract_text(payload_path, payload, media_type, extraction):
    expected_fields = {"tool", "version", "deterministic"}
    if media_type == "application/pdf":
        expected_fields.add("arguments")
    _require_exact_fields(extraction, expected_fields, "text_extraction")
    _require_text(extraction["tool"], "tool")
    _require_text(extraction["version"], "version")
    if extraction["deterministic"] is not True:
        raise SourceEvidenceError("text extraction must be deterministic")
    if media_type == "application/pdf":
        if extraction["tool"] != "pdftotext":
            raise SourceEvidenceError("PDF payload requires pdftotext extraction")
        arguments = extraction["arguments"]
        if arguments != ["-layout", "-enc", "UTF-8"]:
            raise SourceEvidenceError("pdftotext arguments must be deterministic")
        installed_version = _pdftotext_version()
        if extraction["version"] != installed_version:
            raise SourceEvidenceError(
                "recorded pdftotext version does not match installed tool"
            )
        try:
            completed = subprocess.run(
                ["pdftotext", *arguments, str(payload_path), "-"],
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise SourceEvidenceError(f"cannot execute pdftotext: {exc}") from exc
        if completed.returncode != 0:
            diagnostic = completed.stderr.decode("utf-8", errors="replace").strip()
            raise SourceEvidenceError(f"pdftotext extraction failed: {diagnostic}")
        try:
            return completed.stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceEvidenceError("pdftotext output is not UTF-8") from exc
    if media_type in {"application/xml", "text/xml"}:
        if extraction["tool"] != "xml_text_content":
            raise SourceEvidenceError("XML payload requires xml_text_content extraction")
        return _xml_article_text(payload, context="XML payload")
    if media_type.startswith("text/"):
        if extraction["tool"] != "utf8_text":
            raise SourceEvidenceError("text payload requires utf8_text extraction")
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceEvidenceError("text payload is not valid UTF-8") from exc
    raise SourceEvidenceError(f"unsupported offline media type {media_type}")


def _pdftotext_version():
    try:
        completed = subprocess.run(
            ["pdftotext", "-v"], capture_output=True, check=False
        )
    except OSError as exc:
        raise SourceEvidenceError(f"cannot execute pdftotext: {exc}") from exc
    if completed.returncode != 0:
        raise SourceEvidenceError("cannot determine pdftotext version")
    output = completed.stderr or completed.stdout
    first_line = output.decode("utf-8", errors="replace").splitlines()[0]
    prefix = "pdftotext version "
    if not first_line.startswith(prefix) or not first_line[len(prefix) :].strip():
        raise SourceEvidenceError("cannot parse pdftotext version")
    return first_line[len(prefix) :].strip()


def _xml_article_text(payload, *, context):
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise SourceEvidenceError(f"{context} is malformed: {exc}") from exc
    def local_tag(node):
        return node.tag.rsplit("}", 1)[-1].casefold()

    nodes = [node for node in root.iter() if isinstance(node.tag, str)]
    explicit_body_nodes = [
        node for node in nodes if local_tag(node) in {"body", "originaltext", "sections"}
    ]
    if explicit_body_nodes:
        body_nodes = explicit_body_nodes
    else:
        content_tags = {"p", "para", "section"}
        body_nodes = [
            node
            for node in nodes
            if local_tag(node) == "article"
            and any(
                local_tag(descendant) in content_tags
                for descendant in node.iter()
                if isinstance(descendant.tag, str)
            )
        ]
    if not body_nodes:
        raise SourceEvidenceError(f"{context} contains metadata but no article body")
    paragraph_tags = {"p", "para", "simple-para"}
    paragraph_nodes = [
        descendant
        for node in body_nodes
        for descendant in node.iter()
        if isinstance(descendant.tag, str)
        and local_tag(descendant) in paragraph_tags
    ]
    body_text = " ".join(
        text.strip()
        for node in paragraph_nodes
        for text in node.itertext()
        if text.strip()
    )
    if not body_text:
        raise SourceEvidenceError(f"{context} contains no nonempty article body")
    return body_text


def _require_target_anchors(text, anchors):
    if isinstance(anchors, (str, bytes, bytearray)) or not isinstance(
        anchors, Sequence
    ):
        raise SourceEvidenceError("required_search_anchors must be a sequence")
    normalized = text.casefold()
    missing = [
        anchor
        for anchor in anchors
        if not isinstance(anchor, str) or not anchor.strip() or anchor.casefold() not in normalized
    ]
    if missing:
        raise SourceEvidenceError(
            "payload does not contain required target-bearing anchor: "
            + ", ".join(repr(anchor) for anchor in missing)
        )


def _load_json(path):
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise SourceEvidenceError(f"duplicate JSON key {key!r} in {path}")
            result[key] = value
        return result

    def reject_constant(value):
        raise SourceEvidenceError(f"non-finite JSON number {value} in {path}")

    def parse_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            reject_constant(value)
        return parsed

    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            return json.load(
                handle,
                object_pairs_hook=reject_duplicates,
                parse_constant=reject_constant,
                parse_float=parse_float,
            )
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceEvidenceError(f"cannot load provenance JSON {path}: {exc}") from exc


def _require_exact_fields(value, expected, label):
    _require_mapping(value, label)
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing:
        raise SourceEvidenceError(f"{label} missing required field {missing[0]}")
    if extra:
        raise SourceEvidenceError(f"{label} contains unsupported field {extra[0]}")


def _require_mapping(value, label):
    if not isinstance(value, Mapping):
        raise SourceEvidenceError(f"{label} must be a mapping")


def _require_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise SourceEvidenceError(f"{label} must be nonempty text")
