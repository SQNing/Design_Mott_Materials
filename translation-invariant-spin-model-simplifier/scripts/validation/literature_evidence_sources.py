"""Offline verification for authoritative literature source payloads."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import subprocess
from types import MappingProxyType
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


def authoritative_route_for_identity(identity):
    """Return the publisher-specific authoritative acquisition route."""

    _require_mapping(identity, "canonical source identity")
    if set(identity) != {"kind", "value"}:
        raise SourceEvidenceError("canonical source identity must contain kind and value")
    kind = identity["kind"]
    value = identity["value"]
    _require_text(kind, "source identity kind")
    _require_text(value, "source identity value")
    if kind == "arxiv":
        return _route(
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
    if prefix == "10.1103":
        return _route(
            "aps_harvest_pdf",
            f"https://harvest.aps.org/v2/journals/articles/{value}/fulltext",
            "application/pdf",
            "unattended",
        )
    if prefix == "10.1016":
        return _route(
            "elsevier_article_api_xml",
            f"https://api.elsevier.com/content/article/doi/{value}",
            "application/xml",
            "api_key_or_entitlement",
        )
    if prefix == "10.1038":
        return _route(
            "nature_article_pdf",
            f"https://www.nature.com/articles/{suffix}.pdf",
            "application/pdf",
            "authenticated_session",
        )
    if prefix == "10.1007":
        return _route(
            "springer_content_pdf",
            f"https://link.springer.com/content/pdf/{value}.pdf",
            "application/pdf",
            "authenticated_session",
        )
    if prefix == "10.1140":
        return _route(
            "epj_springer_content_pdf",
            f"https://link.springer.com/content/pdf/{value}.pdf",
            "application/pdf",
            "authenticated_session",
        )
    if prefix == "10.1088":
        return _route(
            "iop_article_pdf",
            f"https://iopscience.iop.org/article/{value}/pdf",
            "application/pdf",
            "challenge_or_institutional",
        )
    if prefix == "10.1209":
        return _route(
            "epl_iop_article_pdf",
            f"https://iopscience.iop.org/article/{value}/pdf",
            "application/pdf",
            "challenge_or_institutional",
        )
    if prefix == "10.1126":
        return _route(
            "science_article_pdf",
            f"https://www.science.org/doi/pdf/{value}",
            "application/pdf",
            "challenge_or_institutional",
        )
    if prefix == "10.1063":
        return _route(
            "aip_article_discovery",
            f"https://doi.org/{value}",
            "application/pdf",
            "challenge_or_institutional",
        )
    if prefix == "10.1021":
        return _route(
            "acs_article_pdf",
            f"https://pubs.acs.org/doi/pdf/{value}",
            "application/pdf",
            "challenge_or_institutional",
        )
    if prefix == "10.1143":
        return _route(
            "jpsj_article_pdf",
            f"https://journals.jps.jp/doi/pdf/{value}",
            "application/pdf",
            "challenge_or_institutional",
        )
    if prefix == "10.1002":
        return _route(
            "wiley_book_provisioning",
            f"https://doi.org/{value}",
            "application/pdf",
            "licensed_manual_provisioning",
        )
    raise SourceEvidenceError(f"no authoritative route is declared for DOI prefix {prefix}")


def _route(kind, url, media_type, access_mode):
    return {
        "kind": kind,
        "url": url,
        "expected_media_type": media_type,
        "access_mode": access_mode,
    }


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
    _require_exact_fields(metadata, required, "retrieval_metadata")
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
    status = metadata["http_status"]
    if isinstance(status, bool) or not isinstance(status, int) or not 200 <= status < 300:
        raise SourceEvidenceError("http_status must be a successful integer status")
    _require_mapping(metadata["response_headers"], "response_headers")
    expected_artifact_id = f"{identity['kind']}:{identity['value']}"
    if metadata["immutable_artifact_identifier"] != expected_artifact_id:
        raise SourceEvidenceError("immutable_artifact_identifier disagrees with source identity")


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
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError as exc:
            raise SourceEvidenceError(f"malformed XML payload: {exc}") from exc
        return " ".join(text.strip() for text in root.itertext() if text.strip())
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
