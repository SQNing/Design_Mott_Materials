"""Fetch or verify authoritative literature payloads with fail-closed routing."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import ssl
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ElementTree

from validation.literature_evidence_inventory import load_and_validate_inventory
from validation.literature_evidence_sources import (
    SourceEvidenceError,
    _pdftotext_version,
    arxiv_atom_identifier_matches,
    authoritative_origin_for_route_kind,
    load_verified_source,
    validate_download_response,
    validate_work_identity_document,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_ROOT = PROJECT_ROOT / "source-cache"
DEFAULT_CA_BUNDLE = Path(
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"
)
USER_AGENT = "Design-Mott-Materials-literature-audit/1.0 (offline evidence acquisition)"


def main(argv=None):
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--verify-offline", action="store_true")
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--ca-bundle", type=Path, default=DEFAULT_CA_BUNDLE)
    parser.add_argument(
        "--access-mode",
        choices=("unattended", "all"),
        default="unattended",
    )
    args = parser.parse_args(argv)

    inventory = load_and_validate_inventory()
    source_by_id = {item["source_id"]: item for item in inventory.source_index}
    route_by_id = {
        item["source_id"]: item for item in inventory.source_provisioning
    }
    selected_ids = sorted(source_by_id) if args.all else sorted(set(args.source_id))
    unknown = sorted(set(selected_ids) - set(source_by_id))
    if unknown:
        parser.error("unknown source IDs: " + ", ".join(unknown))

    outcomes = []
    for source_id in selected_ids:
        source = _plain(source_by_id[source_id])
        route = _plain(route_by_id[source_id])
        if route["access_mode"] != "unattended" and args.access_mode != "all":
            outcome = _outcome(
                source_id,
                "blocked",
                f"route requires {route['access_mode']}",
            )
        elif args.verify_offline:
            outcome = _verify_cached_source(args.cache_root, source, route)
        else:
            outcome = _fetch_source(
                args.cache_root,
                source,
                route,
                ca_bundle=args.ca_bundle,
                resume=args.resume,
            )
        outcomes.append(outcome)
        print(json.dumps(outcome, sort_keys=True), flush=True)

    summary = {
        status: sum(item["status"] == status for item in outcomes)
        for status in sorted({item["status"] for item in outcomes})
    }
    print(json.dumps({"summary": summary, "total": len(outcomes)}, sort_keys=True))
    return 0 if all(item["status"] in {"verified", "acquired", "resumed", "blocked"} for item in outcomes) else 1


def _fetch_source(cache_root, source, route, *, ca_bundle, resume):
    source_id = source["source_id"]
    source_dir = Path(cache_root) / source_id
    provenance_path = source_dir / "provenance.json"
    if source_dir.exists():
        if not resume:
            return _outcome(source_id, "failed", "cache directory already exists")
        try:
            load_verified_source(
                source_dir,
                expected_source=source,
                provisioning_route=route,
            )
        except SourceEvidenceError as exc:
            if not _needs_work_identity_sidecar(source_dir, route):
                return _outcome(source_id, "failed", f"existing cache is invalid: {exc}")
            try:
                ssl_context = _ssl_context(ca_bundle)
                evidence = _fetch_work_identity_evidence(source, route, ssl_context)
                _write_work_identity_sidecars(source_dir, evidence)
                load_verified_source(
                    source_dir,
                    expected_source=source,
                    provisioning_route=route,
                )
            except Exception as supplement_exc:
                return _outcome(
                    source_id,
                    "failed",
                    f"existing cache identity supplement failed: {supplement_exc}",
                )
            return _outcome(source_id, "resumed", "existing cache identity evidence added")
        return _outcome(source_id, "resumed", "existing cache verified")
    try:
        ssl_context = _ssl_context(ca_bundle)
        route_spec = {
            **route["authoritative_retrieval_route"],
            "expected_media_type": route["expected_media_type"],
            "access_mode": route["access_mode"],
        }
        response = _download(route_spec, ssl_context)
        bibliographic = _fetch_bibliographic_metadata(source, ssl_context)
        evidence = _fetch_work_identity_evidence(source, route, ssl_context)
        extension = "xml" if route["expected_media_type"] == "application/xml" else "pdf"
        payload_name = f"source.{extension}"
        provenance = _build_provenance(
            source,
            route,
            response,
            bibliographic,
            payload_name=payload_name,
        )
        source_dir.mkdir(parents=True, exist_ok=False)
        with source_dir.joinpath(payload_name).open("xb") as handle:
            handle.write(response["body"])
        with provenance_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(provenance, handle, indent=2, sort_keys=True, ensure_ascii=True)
            handle.write("\n")
        if evidence is not None:
            _write_work_identity_sidecars(source_dir, evidence)
        load_verified_source(
            source_dir,
            expected_source=source,
            provisioning_route=route,
        )
        return _outcome(source_id, "acquired", response["final_url"])
    except Exception as exc:
        return _outcome(source_id, "failed", str(exc))


def _verify_cached_source(cache_root, source, route):
    source_id = source["source_id"]
    try:
        verified = load_verified_source(
            Path(cache_root) / source_id,
            expected_source=source,
            provisioning_route=route,
        )
    except SourceEvidenceError as exc:
        return _outcome(source_id, "failed", str(exc))
    return _outcome(source_id, "verified", verified.payload_sha256)


def _download(route, ssl_context):
    request = Request(
        route["url"],
        headers={
            "Accept": route["expected_media_type"],
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, context=ssl_context, timeout=60) as response:
        body = response.read()
        status = response.status
        headers = dict(response.headers.items())
        final_url = response.geturl()
    media_type = validate_download_response(
        route,
        status=status,
        headers=headers,
        body=body,
        final_url=final_url,
    )
    return {
        "body": body,
        "status": status,
        "headers": headers,
        "final_url": final_url,
        "media_type": media_type,
    }


def _fetch_work_identity_evidence(source, route, ssl_context):
    authoritative_route = route["authoritative_retrieval_route"]
    evidence_route = authoritative_route["work_identity_evidence"]
    if evidence_route["kind"] == "canonical_identity":
        return None
    request = Request(
        evidence_route["url"],
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    with urlopen(request, context=ssl_context, timeout=30) as response:
        payload = response.read()
        if response.status != 200:
            raise SourceEvidenceError(
                f"work identity evidence returned HTTP status {response.status}"
            )
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceEvidenceError(f"work identity evidence is invalid JSON: {exc}") from exc
    validate_work_identity_document(
        document,
        identity=source["canonical_identity"],
        authoritative_route=authoritative_route,
        evidence_kind=evidence_route["kind"],
    )
    return {
        "payload": payload,
        "descriptor": {
            "kind": evidence_route["kind"],
            "url": evidence_route["url"],
            "payload_relative_path": "work-identity.json",
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "payload_byte_length": len(payload),
        },
    }


def _needs_work_identity_sidecar(source_dir, route):
    evidence = route["authoritative_retrieval_route"]["work_identity_evidence"]
    return (
        evidence["kind"] != "canonical_identity"
        and not source_dir.joinpath("work-identity.json").exists()
        and not source_dir.joinpath("work-identity.provenance.json").exists()
    )


def _write_work_identity_sidecars(source_dir, evidence):
    if evidence is None:
        return
    with source_dir.joinpath("work-identity.json").open("xb") as handle:
        handle.write(evidence["payload"])
    with source_dir.joinpath("work-identity.provenance.json").open(
        "x", encoding="utf-8", newline="\n"
    ) as handle:
        json.dump(
            evidence["descriptor"],
            handle,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        handle.write("\n")


def _fetch_bibliographic_metadata(source, ssl_context):
    identity = source["canonical_identity"]
    if identity["kind"] == "doi":
        return _crossref_metadata(identity["value"], ssl_context)
    return _arxiv_metadata(identity["value"], ssl_context)


def _crossref_metadata(doi, ssl_context):
    url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, context=ssl_context, timeout=30) as response:
        document = json.loads(response.read().decode("utf-8"))
    message = document.get("message", {})
    if str(message.get("DOI", "")).lower() != doi.lower():
        raise SourceEvidenceError("Crossref DOI metadata disagrees with source identity")
    title = _first_text(message.get("title"), "Crossref title")
    venue = _first_text(message.get("container-title"), "Crossref venue")
    authors = []
    for author in message.get("author", []):
        rendered = " ".join(
            part for part in (author.get("given", ""), author.get("family", "")) if part
        ).strip()
        if rendered:
            authors.append(rendered)
    if not authors:
        raise SourceEvidenceError("Crossref metadata has no authors")
    publication_date = _crossref_date(message)
    return {
        "title": title,
        "authors": authors,
        "venue": venue,
        "publication_date": publication_date,
    }


def _arxiv_metadata(arxiv_id, ssl_context):
    url = f"https://export.arxiv.org/api/query?id_list={quote(arxiv_id, safe='')}"
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml"})
    with urlopen(request, context=ssl_context, timeout=30) as response:
        payload = response.read()
    root = ElementTree.fromstring(payload)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", namespace)
    if entry is None:
        raise SourceEvidenceError("arXiv metadata response has no entry")
    identifier = (entry.findtext("atom:id", default="", namespaces=namespace)).rstrip("/")
    if not arxiv_atom_identifier_matches(identifier, arxiv_id):
        raise SourceEvidenceError("arXiv metadata identity disagrees with source index")
    title = " ".join(entry.findtext("atom:title", default="", namespaces=namespace).split())
    authors = [
        " ".join(node.findtext("atom:name", default="", namespaces=namespace).split())
        for node in entry.findall("atom:author", namespace)
    ]
    authors = [author for author in authors if author]
    published = entry.findtext("atom:published", default="", namespaces=namespace)
    if not title or not authors or len(published) < 10:
        raise SourceEvidenceError("arXiv metadata is incomplete")
    return {
        "title": title,
        "authors": authors,
        "venue": "arXiv",
        "publication_date": published[:10],
    }


def _build_provenance(source, route, response, bibliographic, *, payload_name):
    body = response["body"]
    identity = source["canonical_identity"]
    retrieval_kind = route["authoritative_retrieval_route"]["kind"]
    retrieval_route = route["authoritative_retrieval_route"]
    origin = authoritative_origin_for_route_kind(retrieval_kind)
    extraction = (
        {
            "tool": "pdftotext",
            "version": _pdftotext_version(),
            "deterministic": True,
            "arguments": ["-layout", "-enc", "UTF-8"],
        }
        if response["media_type"] == "application/pdf"
        else {
            "tool": "xml_text_content",
            "version": "python-stdlib",
            "deterministic": True,
        }
    )
    return {
        "schema_version": 1,
        "source_id": source["source_id"],
        "source_identity": {
            "kind": identity["kind"],
            "value": identity["value"],
            "canonical_url": source["canonical_url"],
        },
        "bibliographic_metadata": bibliographic,
        "retrieval_metadata": {
            "url": response["final_url"],
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "method": retrieval_kind,
            "authoritative_origin": origin,
            "http_status": response["status"],
            "response_headers": _stable_response_headers(response["headers"]),
            "immutable_artifact_identifier": retrieval_route["artifact_identifier"],
            **(
                {"work_identity_evidence": retrieval_route["work_identity_evidence"]}
                if retrieval_route["work_identity_evidence"]["kind"]
                != "canonical_identity"
                else {}
            ),
        },
        "media_type": response["media_type"],
        "raw_payload_sha256": hashlib.sha256(body).hexdigest(),
        "raw_payload_byte_length": len(body),
        "payload_relative_path": payload_name,
        "artifact_coordinates": {
            "kind": "whole_payload",
            "start_byte": 0,
            "end_byte": len(body),
        },
        "license_access_notes": {
            "access_status": "retrieved_from_authoritative_route",
            "redistributability": "unresolved",
            "notes": "Local audit cache; redistribution requires separate review.",
        },
        "citation_metadata_verification": {
            "status": "verified",
            "verified_fields": ["title", "authors", "venue", "publication_date", identity["kind"]],
        },
        "text_extraction": extraction,
    }


def _ssl_context(ca_bundle):
    if not Path(ca_bundle).is_file():
        raise SourceEvidenceError(f"CA bundle is unavailable: {ca_bundle}")
    return ssl.create_default_context(cafile=str(ca_bundle))


def _first_text(values, label):
    if not isinstance(values, list) or not values or not str(values[0]).strip():
        raise SourceEvidenceError(f"{label} is missing")
    return str(values[0]).strip()


def _crossref_date(message):
    for key in ("published-print", "published-online", "issued", "created"):
        parts = message.get(key, {}).get("date-parts", [])
        if not parts or not parts[0]:
            continue
        values = list(parts[0]) + [1, 1]
        year, month, day = values[:3]
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    raise SourceEvidenceError("Crossref publication date is missing")


def _stable_response_headers(headers):
    allowed = {"content-type", "content-length", "etag", "last-modified"}
    return {
        key.lower(): str(value)
        for key, value in headers.items()
        if key.lower() in allowed
    }


def _outcome(source_id, status, detail):
    return {"source_id": source_id, "status": status, "detail": detail}


def _plain(value):
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if hasattr(value, "items"):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


if __name__ == "__main__":
    sys.exit(main())
