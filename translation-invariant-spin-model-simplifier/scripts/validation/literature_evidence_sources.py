"""Offline verification for authoritative literature source payloads."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess
from types import MappingProxyType
from urllib.parse import urljoin, urlparse
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
    "10.1140/epjb/e2006-00273-y": ("cond-mat/0604023", "W1983899391"),
    "10.1140/epjb/e2015-60113-7": ("1505.07219", "W2115824467"),
}
_INSTITUTIONAL_REPOSITORY_ROUTES = {
    "10.1021/cm504242t": {
        "url": "https://www.osti.gov/servlets/purl/1185798",
        "artifact_identifier": "osti:1185798",
        "work_identity_evidence": {
            "kind": "osti_same_work_fulltext",
            "url": "https://www.osti.gov/api/v1/records/1185798",
        },
    },
}
_OPEN_PUBLISHER_ROUTES = {
    "10.1038/ncomms14113": ("ncomms14113", "W2591608240"),
    "10.1038/ncomms2914": ("ncomms2914", "W2068740639"),
    "10.1038/ncomms3287": ("ncomms3287", "W2103622306"),
    "10.1038/ncomms5203": ("ncomms5203", "W2013284845"),
    "10.1038/ncomms6137": ("ncomms6137", "W1695352508"),
    "10.1038/srep16419": ("srep16419", "W3105052732"),
}
_EXACT_AUTHORITATIVE_ROUTES = {
    "10.1143/ptp.5.2.177": {
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
    "10.1088/0305-4470/17/13/020": {
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
    "10.1088/0305-4470/16/10/023": {
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
    },
    "10.1038/s41535-026-00868-6": {
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
}


def payload_extension_for_media_type(media_type):
    """Return the only permitted cache extension for a supported payload."""

    extensions = {
        "application/pdf": "pdf",
        "application/xml": "xml",
        "text/html": "html",
    }
    try:
        return extensions[media_type]
    except (KeyError, TypeError) as exc:
        raise SourceEvidenceError(
            f"unsupported authoritative media type {media_type!r}"
        ) from exc


def authoritative_origin_for_route_kind(route_kind):
    """Return the provenance origin implied by an acquisition route."""

    return {
        "arxiv_export_pdf": "arxiv",
        "arxiv_author_manuscript_pdf": "author_repository",
        "institutional_repository_pdf": "institutional_repository",
        "author_repository_pdf": "author_repository",
        "oup_minimal_html": "publisher",
        "nature_open_article_pdf": "publisher",
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
    exact_route = _EXACT_AUTHORITATIVE_ROUTES.get(value.casefold())
    if exact_route is not None:
        return {
            key: (
                dict(item)
                if key == "work_identity_evidence"
                else item
            )
            for key, item in exact_route.items()
        }
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
            work_identity_evidence=institutional_route["work_identity_evidence"],
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
            "download media type does not match authoritative route"
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
    elif expected == "text/html":
        visible_text, html_hrefs, html_doi_metadata = _html_visible_document(
            body,
            context="downloaded HTML",
        )
        lowered = visible_text.casefold()
        challenge_markers = (
            "access denied",
            "verify you are human",
            "captcha",
            "cloudflare",
            "enable javascript and cookies",
        )
        if any(marker in lowered for marker in challenge_markers):
            raise SourceEvidenceError("downloaded HTML is a challenge or access-denied page")
        if route.get("kind") == "oup_minimal_html":
            _validate_husimi_syozi_visible_text(
                visible_text,
                hrefs=html_hrefs,
                doi_metadata=html_doi_metadata,
            )
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
        raw["bibliographic_metadata"],
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
    expected_suffix = "." + payload_extension_for_media_type(media_type)
    if payload_path.suffix.casefold() != expected_suffix:
        raise SourceEvidenceError("payload extension disagrees with payload media type")
    extracted_text = _extract_text(
        payload_path, payload, media_type, raw["text_extraction"]
    )
    route_kind = provisioning_route.get("authoritative_retrieval_route", {}).get(
        "kind"
    )
    if route_kind == "oup_minimal_html":
        _validate_husimi_syozi_html_payload(
            payload,
            context="OUP offline HTML payload",
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
    _validate_serialized_https_url(metadata["url"], "retrieval metadata URL")
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
        _validate_serialized_https_url(
            stored.get("url"), "work identity evidence URL"
        )
        if not _same_work_identity_route(stored, evidence):
            raise SourceEvidenceError("work identity evidence route disagrees with provisioning")
        allowed = {
            "kind",
            "url",
            "media_type",
            "payload_relative_path",
            "payload_sha256",
            "payload_byte_length",
        }
        legacy_allowed = allowed - {"media_type"}
        if set(stored) not in ({"kind", "url"}, legacy_allowed, allowed):
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


def _validate_serialized_https_url(value, label):
    try:
        parsed = urlparse(value)
        _ = parsed.port
    except ValueError:
        raise SourceEvidenceError(f"{label} is invalid") from None
    if parsed.username is not None or parsed.password is not None:
        raise SourceEvidenceError(f"{label} contains forbidden userinfo")
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise SourceEvidenceError(f"{label} must be an HTTPS URL")
    if parsed.query or parsed.fragment:
        raise SourceEvidenceError(
            f"{label} must not serialize a query or fragment"
        )


def _validate_work_identity_payload(
    root, metadata, identity, provisioning_route, bibliographic_metadata
):
    route = provisioning_route.get("authoritative_retrieval_route", {})
    expected = route.get("work_identity_evidence", {})
    if expected.get("kind") in {None, "canonical_identity"}:
        return
    stored = metadata["work_identity_evidence"]
    if "payload_relative_path" in stored:
        descriptor = stored
    else:
        descriptor = _load_json(root / "work-identity.provenance.json")
        _require_mapping(descriptor, "work identity sidecar provenance")
        descriptor_fields = {
            "kind",
            "url",
            "media_type",
            "payload_relative_path",
            "payload_sha256",
            "payload_byte_length",
        }
        if set(descriptor) not in (
            descriptor_fields,
            descriptor_fields - {"media_type"},
        ):
            raise SourceEvidenceError(
                "work identity sidecar provenance has invalid fields"
            )
        if not _same_work_identity_route(descriptor, stored):
            raise SourceEvidenceError("work identity sidecar disagrees with source provenance")
    _validate_serialized_https_url(
        descriptor.get("url"), "work identity sidecar URL"
    )
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
    media_type = descriptor.get("media_type", "application/json")
    expected_media_type = (
        "text/html"
        if descriptor["kind"] == "author_publications_same_work"
        else "application/json"
    )
    if media_type != expected_media_type:
        raise SourceEvidenceError(
            "work identity evidence media type disagrees with evidence kind"
        )
    expected_name = (
        "work-identity.html" if media_type == "text/html" else "work-identity.json"
    )
    if descriptor["payload_relative_path"] != expected_name:
        raise SourceEvidenceError(
            "work identity evidence payload name disagrees with media type"
        )
    document = payload if media_type == "text/html" else _load_json(evidence_path)
    validate_work_identity_document(
        document,
        identity=identity,
        authoritative_route=route,
        evidence_kind=descriptor["kind"],
        bibliographic_metadata={
            **bibliographic_metadata,
            "doi": identity.get("value", ""),
        },
    )


def validate_work_identity_document(
    document,
    *,
    identity,
    authoritative_route,
    evidence_kind,
    bibliographic_metadata=None,
):
    """Prove that an external work record links a DOI to the retrieved artifact."""

    canonical_doi = identity.get("value", "").casefold()
    artifact_identifier = authoritative_route.get("artifact_identifier", "")
    if evidence_kind == "author_publications_same_work":
        _validate_author_publications_same_work(
            document,
            canonical_doi=canonical_doi,
            authoritative_route=authoritative_route,
            bibliographic_metadata=bibliographic_metadata,
        )
        return
    if evidence_kind == "osti_same_work_fulltext":
        if (
            not isinstance(document, list)
            or not document
            or not isinstance(document[0], Mapping)
        ):
            raise SourceEvidenceError(
                "OSTI work identity evidence must be a nonempty record list"
            )
        record = document[0]
        if str(record.get("doi", "")).casefold() != canonical_doi:
            raise SourceEvidenceError("work identity evidence canonical DOI mismatch")
        links = record.get("links")
        if not isinstance(links, list):
            raise SourceEvidenceError("OSTI work identity evidence has no links")
        location_urls = {
            link.get("href")
            for link in links
            if isinstance(link, Mapping)
            and link.get("rel") == "fulltext"
            and isinstance(link.get("href"), str)
        }
    else:
        _require_mapping(document, "work identity evidence document")
    if evidence_kind == "core_same_work_output":
        expected_output_id = artifact_identifier.removeprefix("core:")
        if not expected_output_id or str(document.get("id", "")) != expected_output_id:
            raise SourceEvidenceError("work identity evidence CORE output ID mismatch")
        if str(document.get("doi", "")).casefold() != canonical_doi:
            raise SourceEvidenceError("work identity evidence canonical DOI mismatch")
        authors = document.get("authors")
        if not isinstance(authors, list):
            raise SourceEvidenceError("work identity evidence CORE authors are missing")
        author_names = [
            author.get("name") if isinstance(author, Mapping) else author
            for author in authors
        ]
        _validate_same_work_bibliographic_metadata(
            canonical_doi=canonical_doi,
            title=document.get("title"),
            authors=author_names,
            bibliographic_metadata=bibliographic_metadata,
        )
        location_urls = {
            document.get(field)
            for field in ("downloadUrl", "fullTextLink", "pdfUrl")
            if isinstance(document.get(field), str)
        }
    elif evidence_kind.startswith("openalex_"):
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
    elif evidence_kind != "osti_same_work_fulltext":
        raise SourceEvidenceError(
            f"unsupported work identity evidence kind {evidence_kind}"
        )
    if not _artifact_location_matches(
        artifact_identifier,
        authoritative_route.get("url", ""),
        location_urls,
    ):
        raise SourceEvidenceError("work identity evidence does not locate the retrieved artifact")


def _normalize_work_text(value):
    if not isinstance(value, str) or not value.strip():
        return ""
    return " ".join(re.findall(r"[a-z0-9]+", unescape(value).casefold()))


def _validate_same_work_bibliographic_metadata(
    *, canonical_doi, title, authors, bibliographic_metadata
):
    _require_mapping(bibliographic_metadata, "work identity bibliographic metadata")
    if str(bibliographic_metadata.get("doi", "")).casefold() != canonical_doi:
        raise SourceEvidenceError("work identity DOI bibliographic metadata mismatch")
    expected_title = _normalize_work_text(bibliographic_metadata.get("title"))
    if not expected_title or _normalize_work_text(title) != expected_title:
        raise SourceEvidenceError("work identity bibliographic title mismatch")
    expected_authors = bibliographic_metadata.get("authors")
    if (
        not isinstance(expected_authors, Sequence)
        or isinstance(expected_authors, (str, bytes, bytearray))
        or not expected_authors
    ):
        raise SourceEvidenceError("work identity bibliographic authors are missing")
    if (
        not isinstance(authors, Sequence)
        or isinstance(authors, (str, bytes, bytearray))
        or not authors
    ):
        raise SourceEvidenceError("work identity evidence authors are missing")
    expected = {_normalize_work_text(author) for author in expected_authors}
    reported = {_normalize_work_text(author) for author in authors}
    if "" in expected or "" in reported or reported != expected:
        raise SourceEvidenceError("work identity bibliographic authors mismatch")


_VISIBLE_BLOCK_ELEMENTS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "br",
    "dd",
    "div",
    "dl",
    "dt",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}


class _RenderedTextBlocks:
    def __init__(self):
        self.parts = []

    def boundary(self):
        if not self.parts or self.parts[-1] is not None:
            self.parts.append(None)

    def append(self, value):
        rendered = re.sub(r"\s+", " ", unescape(value))
        if rendered:
            self.parts.append(rendered)

    def blocks(self):
        blocks = []
        current = []
        for part in (*self.parts, None):
            if part is None:
                normalized = " ".join("".join(current).split())
                if normalized:
                    blocks.append(normalized)
                current = []
            else:
                current.append(part)
        return tuple(blocks)


class _VisiblePublicationRecordParser(HTMLParser):
    _VOID_ELEMENTS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
    _ALWAYS_HIDDEN = {"script", "style", "noscript", "template"}
    _RECORD_TAGS = {"article", "li", "tr"}
    _RECORD_CLASSES = {
        "publication",
        "publication-item",
        "publication-record",
    }
    _DOI_META_NAMES = {
        "citation_doi",
        "dc.identifier",
        "dc.identifier.doi",
        "prism.doi",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.frames = []
        self.records = []

    def handle_starttag(self, tag, attrs):
        tag = tag.casefold()
        attributes = {str(key).casefold(): value for key, value in attrs}
        style = str(attributes.get("style") or "").casefold()
        parent_hidden = self.frames[-1][1] if self.frames else False
        hidden = parent_hidden or tag in self._ALWAYS_HIDDEN or (
            "hidden" in attributes
            or str(attributes.get("aria-hidden", "")).casefold() == "true"
            or (
                tag == "input"
                and str(attributes.get("type", "")).casefold() == "hidden"
            )
            or re.search(
                r"(?:^|;)\s*display\s*:\s*none(?:\s*!important)?\s*(?:;|$)",
                style,
            )
            is not None
            or re.search(
                r"(?:^|;)\s*visibility\s*:\s*hidden(?:\s*!important)?\s*(?:;|$)",
                style,
            )
            is not None
        )
        parent_record = self.frames[-1][2] if self.frames else None
        parent_body = self.frames[-1][3] if self.frames else False
        in_body = tag == "body" or parent_body
        class_names = set(str(attributes.get("class") or "").casefold().split())
        starts_record = (
            in_body
            and not hidden
            and parent_record is None
            and (
                tag in self._RECORD_TAGS
                or bool(class_names & self._RECORD_CLASSES)
            )
        )
        if starts_record:
            record_index = len(self.records)
            self.records.append(
                {
                    "text_builder": _RenderedTextBlocks(),
                    "hrefs": [],
                    "doi_metadata": [],
                }
            )
        else:
            record_index = parent_record

        if record_index is not None and not hidden:
            record = self.records[record_index]
            if tag in _VISIBLE_BLOCK_ELEMENTS:
                record["text_builder"].boundary()
            href = attributes.get("href")
            if tag == "a" and isinstance(href, str) and href.strip():
                record["hrefs"].append(unescape(href.strip()))
            if tag == "meta" and str(
                attributes.get("name", "")
            ).casefold() in self._DOI_META_NAMES:
                content = attributes.get("content")
                if isinstance(content, str) and content.strip():
                    record["doi_metadata"].append(unescape(content.strip()))
            for name in ("data-doi", "doi"):
                value = attributes.get(name)
                if isinstance(value, str) and value.strip():
                    record["doi_metadata"].append(unescape(value.strip()))

        if tag not in self._VOID_ELEMENTS:
            self.frames.append((tag, hidden, record_index, in_body))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.casefold() not in self._VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.casefold()
        if not self.frames or self.frames[-1][0] != tag:
            raise SourceEvidenceError(
                "work identity author publications HTML is malformed"
            )
        _, hidden, record_index, _ = self.frames[-1]
        if (
            record_index is not None
            and not hidden
            and tag in _VISIBLE_BLOCK_ELEMENTS
        ):
            self.records[record_index]["text_builder"].boundary()
        self.frames.pop()

    def handle_data(self, data):
        if not self.frames:
            return
        _, hidden, record_index, _ = self.frames[-1]
        if hidden or record_index is None:
            return
        self.records[record_index]["text_builder"].append(data)


_DOI_VALUE_PATTERN = r"10\.[0-9]{4,9}/[^\s<>\"']+"
_PLAIN_DOI_VALUE = re.compile(rf"{_DOI_VALUE_PATTERN}\Z", flags=re.IGNORECASE)
_LABELLED_DOI_VALUE = re.compile(
    rf"doi\s*:\s*(?P<value>{_DOI_VALUE_PATTERN})\Z",
    flags=re.IGNORECASE,
)
_TEXT_DOI_VALUE = re.compile(
    rf"(?<![a-z0-9])(?P<value>{_DOI_VALUE_PATTERN})",
    flags=re.IGNORECASE,
)
_ANY_DOI_VALUE = re.compile(_DOI_VALUE_PATTERN, flags=re.IGNORECASE)
_DOI_RESOLVER_MARKER = re.compile(
    r"doi\.org(?::[0-9]+)?/",
    flags=re.IGNORECASE,
)


def _plain_doi_value(value):
    if not isinstance(value, str):
        return None
    rendered = unescape(value).strip()
    match = _PLAIN_DOI_VALUE.fullmatch(rendered)
    return match.group(0).casefold() if match is not None else None


def _resolver_doi_value(value):
    if not isinstance(value, str):
        return None
    rendered = unescape(value).strip()
    try:
        parsed = urlparse(rendered)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.casefold() != "https"
        or parsed.hostname is None
        or parsed.hostname.casefold() != "doi.org"
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.params
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith("/")
    ):
        return None
    return _plain_doi_value(parsed.path[1:])


def _structured_metadata_doi_value(value):
    if not isinstance(value, str):
        return None
    rendered = unescape(value).strip()
    plain = _plain_doi_value(rendered)
    if plain is not None:
        return plain
    resolver = _resolver_doi_value(rendered)
    if resolver is not None:
        return resolver
    labelled = _LABELLED_DOI_VALUE.fullmatch(rendered)
    if labelled is None:
        return None
    return _plain_doi_value(labelled.group("value"))


def _text_token_bounds(text, start, end):
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    while end < len(text) and not text[end].isspace():
        end += 1
    return start, end


def _trim_visible_url_presentation(token):
    rendered = token.strip()
    if (
        len(rendered) >= 2
        and rendered[0] in "([{"
        and rendered[-1] == {"(": ")", "[": "]", "{": "}"}[rendered[0]]
    ):
        rendered = rendered[1:-1]
    if rendered.endswith(","):
        rendered = rendered[:-1]
    if rendered.endswith("."):
        rendered = rendered[:-1]
    return rendered


def _unmatched_open_parenthesis(text):
    depth = 0
    for character in text:
        if character == "(":
            depth += 1
        elif character == ")" and depth:
            depth -= 1
    return depth > 0


def _normalized_text_doi_value(text, match):
    value = match.group("value")
    following = text[match.end() :]
    preceding = text[: match.start()]
    if value.endswith(",") and (not following or following[0].isspace()):
        value = value[:-1]
    if value.endswith(")") and (
        value.count(")") > value.count("(")
        and _unmatched_open_parenthesis(preceding)
    ):
        value = value[:-1]
    if value.endswith(".") and not following:
        value = value[:-1]
    return _plain_doi_value(value)


def _visible_text_doi_values(blocks):
    values = set()
    valid_carriers = True
    for block in blocks:
        for marker in _DOI_RESOLVER_MARKER.finditer(block):
            token_start, token_end = _text_token_bounds(
                block,
                marker.start(),
                marker.end(),
            )
            token = _trim_visible_url_presentation(
                block[token_start:token_end]
            )
            if _resolver_doi_value(token) is None:
                valid_carriers = False
        for match in _TEXT_DOI_VALUE.finditer(block):
            value = _normalized_text_doi_value(block, match)
            if value is None:
                valid_carriers = False
                continue
            values.add(value)
            token_start, token_end = _text_token_bounds(
                block,
                match.start(),
                match.end(),
            )
            prefix = block[token_start : match.start()]
            if "://" in prefix or _DOI_RESOLVER_MARKER.search(prefix):
                token = _trim_visible_url_presentation(
                    block[token_start:token_end]
                )
                if _resolver_doi_value(token) != value:
                    valid_carriers = False
    return values, valid_carriers


def _doi_values_are_exact(values, canonical_doi, *, valid_carriers):
    expected = _plain_doi_value(canonical_doi)
    return valid_carriers and expected is not None and values == {expected}


def _record_text_blocks(record):
    return record["text_builder"].blocks()


def _add_structured_doi_carriers(values, valid_carriers, hrefs, doi_metadata):
    for href in hrefs:
        if _ANY_DOI_VALUE.search(href) or _DOI_RESOLVER_MARKER.search(href):
            value = _resolver_doi_value(href)
            if value is None:
                valid_carriers = False
            else:
                values.add(value)
    for metadata in doi_metadata:
        value = _structured_metadata_doi_value(metadata)
        if value is None:
            valid_carriers = False
        else:
            values.add(value)
    return values, valid_carriers


def _record_has_exact_doi(record, canonical_doi):
    values, valid_carriers = _visible_text_doi_values(
        _record_text_blocks(record)
    )
    values, valid_carriers = _add_structured_doi_carriers(
        values,
        valid_carriers,
        record["hrefs"],
        record["doi_metadata"],
    )
    return _doi_values_are_exact(
        values,
        canonical_doi,
        valid_carriers=valid_carriers,
    )


def _validate_author_publications_same_work(
    document,
    *,
    canonical_doi,
    authoritative_route,
    bibliographic_metadata,
):
    _html_visible_text(document, context="author publications work identity")
    _require_mapping(bibliographic_metadata, "work identity bibliographic metadata")
    if str(bibliographic_metadata.get("doi", "")).casefold() != canonical_doi:
        raise SourceEvidenceError("work identity DOI bibliographic metadata mismatch")
    expected_title = _normalize_work_text(bibliographic_metadata.get("title"))
    authors = bibliographic_metadata.get("authors")
    if (
        not expected_title
        or not isinstance(authors, Sequence)
        or isinstance(authors, (str, bytes, bytearray))
        or not authors
        or any(not _normalize_work_text(author) for author in authors)
    ):
        raise SourceEvidenceError(
            "work identity author page bibliographic metadata is incomplete"
        )

    parser = _VisiblePublicationRecordParser()
    try:
        parser.feed(document.decode("utf-8"))
        parser.close()
    except Exception as exc:
        if isinstance(exc, SourceEvidenceError):
            raise
        raise SourceEvidenceError(
            f"work identity author publications HTML is malformed: {exc}"
        ) from exc
    evidence_url = authoritative_route.get("work_identity_evidence", {}).get("url", "")
    retrieval_url = authoritative_route.get("url")
    records_with_doi = [
        record
        for record in parser.records
        if _record_has_exact_doi(record, canonical_doi)
    ]
    if not records_with_doi:
        raise SourceEvidenceError(
            "work identity author page canonical DOI mismatch"
        )
    expected_authors = [_normalize_work_text(author) for author in authors]
    for record in records_with_doi:
        normalized_text = _normalize_work_text(
            " ".join(_record_text_blocks(record))
        )
        resolved_links = {urljoin(evidence_url, href) for href in record["hrefs"]}
        if (
            expected_title in normalized_text
            and all(author in normalized_text for author in expected_authors)
            and retrieval_url in resolved_links
        ):
            return
    raise SourceEvidenceError(
        "work identity author page has no single visible publication record "
        "binding title, authors, DOI, and PDF"
    )


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
    if media_type in {"application/pdf", "text/html"}:
        expected_fields.add("arguments")
    _require_exact_fields(extraction, expected_fields, "text_extraction")
    _require_text(extraction["tool"], "tool")
    if extraction["deterministic"] is not True:
        raise SourceEvidenceError("text extraction must be deterministic")
    if media_type == "application/pdf":
        _require_text(extraction["version"], "version")
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
        _require_text(extraction["version"], "version")
        if extraction["tool"] != "xml_text_content":
            raise SourceEvidenceError("XML payload requires xml_text_content extraction")
        return _xml_article_text(payload, context="XML payload")
    if media_type == "text/html":
        if extraction != {
            "tool": "stdlib_html_visible_text",
            "version": 1,
            "deterministic": True,
            "arguments": [],
        }:
            raise SourceEvidenceError(
                "HTML payload requires deterministic stdlib_html_visible_text version 1"
            )
        return _html_visible_text(payload, context="HTML payload")
    if media_type.startswith("text/"):
        _require_text(extraction["version"], "version")
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


class _VisibleArticleHTMLParser(HTMLParser):
    _VOID_ELEMENTS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
    _ALWAYS_HIDDEN = {"script", "style", "noscript", "template"}

    def __init__(self, *, context):
        super().__init__(convert_charrefs=True)
        self.context = context
        self.frames = []
        self.root_seen = False
        self.root_closed = False
        self.body_seen = False
        self.body_closed = False
        self.article_seen = False
        self.visible_text = _RenderedTextBlocks()
        self.hrefs = []
        self.doi_metadata = []

    def handle_starttag(self, tag, attrs):
        tag = tag.casefold()
        if self.root_closed:
            raise SourceEvidenceError(f"{self.context} is malformed after document root")
        if not self.frames:
            if self.root_seen or tag != "html":
                raise SourceEvidenceError(f"{self.context} document root must be html")
            self.root_seen = True
        elif tag == "html":
            raise SourceEvidenceError(f"{self.context} contains a nested document root")
        if tag == "body":
            if (
                self.body_seen
                or not self.frames
                or self.frames[-1][0] != "html"
            ):
                raise SourceEvidenceError(
                    f"{self.context} contains an invalid document body"
                )
            self.body_seen = True
        elif self.body_closed:
            raise SourceEvidenceError(
                f"{self.context} is malformed after document body"
            )

        attributes = {str(key).casefold(): value for key, value in attrs}
        style = str(attributes.get("style") or "").casefold()
        parent_hidden = self.frames[-1][1] if self.frames else False
        hidden = parent_hidden or tag in self._ALWAYS_HIDDEN or (
            "hidden" in attributes
            or str(attributes.get("aria-hidden", "")).casefold() == "true"
            or (
                tag == "input"
                and str(attributes.get("type", "")).casefold() == "hidden"
            )
            or re.search(r"(?:^|;)\s*display\s*:\s*none(?:\s*!important)?\s*(?:;|$)", style)
            is not None
            or re.search(r"(?:^|;)\s*visibility\s*:\s*hidden(?:\s*!important)?\s*(?:;|$)", style)
            is not None
        )
        parent_article = self.frames[-1][2] if self.frames else False
        parent_body = self.frames[-1][3] if self.frames else False
        in_body = tag == "body" or parent_body
        class_names = set(str(attributes.get("class") or "").casefold().split())
        article_container = (
            in_body
            and (
                tag in {"article", "main"}
                or "minimal-article-container" in class_names
            )
        )
        in_article = parent_article or (article_container and not hidden)
        if article_container and not hidden:
            self.article_seen = True
        if in_article and not hidden:
            if tag in _VISIBLE_BLOCK_ELEMENTS:
                self.visible_text.boundary()
            href = attributes.get("href")
            if tag == "a" and isinstance(href, str) and href.strip():
                self.hrefs.append(unescape(href.strip()))
            if tag == "meta" and str(
                attributes.get("name", "")
            ).casefold() in _VisiblePublicationRecordParser._DOI_META_NAMES:
                content = attributes.get("content")
                if isinstance(content, str) and content.strip():
                    self.doi_metadata.append(unescape(content.strip()))
            for name in ("data-doi", "doi"):
                value = attributes.get(name)
                if isinstance(value, str) and value.strip():
                    self.doi_metadata.append(unescape(value.strip()))
        if tag not in self._VOID_ELEMENTS:
            self.frames.append((tag, hidden, in_article, in_body))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.casefold() not in self._VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.casefold()
        if not self.frames or self.frames[-1][0] != tag:
            raise SourceEvidenceError(f"{self.context} is malformed HTML nesting")
        _, hidden, in_article, _ = self.frames[-1]
        if in_article and not hidden and tag in _VISIBLE_BLOCK_ELEMENTS:
            self.visible_text.boundary()
        self.frames.pop()
        if tag == "body":
            self.body_closed = True
        if tag == "html":
            self.root_closed = True

    def handle_data(self, data):
        if not self.frames:
            if data.strip():
                raise SourceEvidenceError(
                    f"{self.context} has visible data outside the document root"
                )
            return
        _, hidden, in_article, _ = self.frames[-1]
        if hidden or not in_article:
            return
        self.visible_text.append(data)

    def result(self):
        if not self.root_seen or not self.root_closed:
            raise SourceEvidenceError(f"{self.context} has no complete document root")
        if not self.body_seen or not self.body_closed:
            raise SourceEvidenceError(f"{self.context} has no complete document body")
        if self.frames:
            raise SourceEvidenceError(f"{self.context} is malformed HTML")
        visible_blocks = self.visible_text.blocks()
        if not self.article_seen or not visible_blocks:
            raise SourceEvidenceError(
                f"{self.context} contains no nonempty visible article body"
            )
        return "\n".join(visible_blocks)


def _html_visible_document(payload, *, context):
    try:
        document = payload.decode("utf-8")
    except (AttributeError, UnicodeDecodeError) as exc:
        raise SourceEvidenceError(f"{context} is not valid UTF-8") from exc
    parser = _VisibleArticleHTMLParser(context=context)
    try:
        parser.feed(document)
        parser.close()
    except SourceEvidenceError:
        raise
    except Exception as exc:
        raise SourceEvidenceError(f"{context} is malformed HTML: {exc}") from exc
    return parser.result(), tuple(parser.hrefs), tuple(parser.doi_metadata)


def _html_visible_text(payload, *, context):
    visible_text, _, _ = _html_visible_document(payload, context=context)
    return visible_text


def _validate_husimi_syozi_visible_text(
    visible_text,
    *,
    hrefs=(),
    doi_metadata=(),
):
    normalized = " ".join(visible_text.split())
    if "The Statistics of Honeycomb and Triangular Lattice. I" not in normalized:
        raise SourceEvidenceError("OUP HTML is missing the exact article title")
    doi_values, valid_doi_carriers = _visible_text_doi_values(
        visible_text.splitlines()
    )
    doi_values, valid_doi_carriers = _add_structured_doi_carriers(
        doi_values,
        valid_doi_carriers,
        hrefs,
        doi_metadata,
    )
    if not _doi_values_are_exact(
        doi_values,
        "10.1143/ptp.5.2.177",
        valid_carriers=valid_doi_carriers,
    ):
        raise SourceEvidenceError("OUP HTML is missing the canonical DOI")
    if "Kodi Husimi" not in normalized or not re.search(
        r"Itiro\s+Sy(?:o|ô)zi", normalized, flags=re.IGNORECASE
    ):
        raise SourceEvidenceError("OUP HTML is missing the article author anchors")
    if "Summary" not in normalized:
        raise SourceEvidenceError("OUP HTML is missing visible article summary text")
    equations = (
        r"(?:ch|cosh)\s*\(?\s*2\s*H\s*\)?\s*=\s*2",
        r"exp\s*\(\s*4\s*H\s*\)\s*=\s*3",
    )
    if any(re.search(pattern, normalized, flags=re.IGNORECASE) is None for pattern in equations):
        raise SourceEvidenceError("OUP HTML is missing a target Curie-point equation")


def _validate_husimi_syozi_html_payload(payload, *, context):
    visible_text, hrefs, doi_metadata = _html_visible_document(
        payload,
        context=context,
    )
    _validate_husimi_syozi_visible_text(
        visible_text,
        hrefs=hrefs,
        doi_metadata=doi_metadata,
    )


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
