"""Fetch or verify authoritative literature payloads with fail-closed routing."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import stat
import sys
from urllib.parse import quote, unquote, urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
    urlopen,
)
import xml.etree.ElementTree as ElementTree

from validation.literature_evidence_inventory import load_and_validate_inventory
from validation.literature_evidence_sources import (
    SourceEvidenceError,
    _pdftotext_version,
    arxiv_atom_identifier_matches,
    authoritative_origin_for_route_kind,
    load_verified_source,
    payload_extension_for_media_type,
    validate_download_response,
    validate_work_identity_document,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_ROOT = PROJECT_ROOT / "source-cache"
DEFAULT_CA_BUNDLE = Path(
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"
)
USER_AGENT = "Design-Mott-Materials-literature-audit/1.0 (offline evidence acquisition)"
_CREDENTIAL_HEADER_NAMES = {
    "Cookie",
    "Authorization",
    "X-ELS-APIKey",
    "X-ELS-Insttoken",
}
_CREDENTIAL_HEADER_NAMES_CASEFOLDED = {
    name.casefold() for name in _CREDENTIAL_HEADER_NAMES
}
_INSTITUTION_NETWORK_ACCESS_MODES = {
    "challenge_or_institutional",
    "api_key_or_entitlement",
}
_EXTRA_AUTHORIZATION_ORIGINS_BY_ROUTE_KIND = {
    "elsevier_article_api_xml": {"https://api.elsevier.com"},
    "nature_article_pdf": {
        "https://www.nature.com",
        "https://idp.nature.com",
    },
    "springer_content_pdf": {"https://link.springer.com"},
    "iop_article_pdf": {"https://iopscience.iop.org"},
    "epl_iop_article_pdf": {"https://iopscience.iop.org"},
    "science_article_pdf": {"https://www.science.org"},
    "aip_article_discovery": {
        "https://doi.org",
        "https://pubs.aip.org",
    },
    "acs_article_pdf": {"https://pubs.acs.org"},
    "jpsj_article_pdf": {"https://journals.jps.jp"},
}


def _path_is_within(path, root):
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _nearest_repository_root(start):
    resolved_start = Path(start).resolve()
    for candidate in (resolved_start, *resolved_start.parents):
        try:
            marker_stat = candidate.joinpath(".git").lstat()
        except OSError:
            continue
        if stat.S_ISDIR(marker_stat.st_mode) or stat.S_ISREG(marker_stat.st_mode):
            return candidate
    raise SourceEvidenceError("containing Git repository root is unavailable")


def _json_without_duplicate_keys(text):
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise SourceEvidenceError("credential JSON contains a duplicate field")
            result[key] = value
        return result

    try:
        return json.loads(text, object_pairs_hook=reject_duplicates)
    except SourceEvidenceError:
        raise
    except (TypeError, json.JSONDecodeError):
        raise SourceEvidenceError("credential file is not valid JSON") from None


def _read_checked_credential_file(path, expected_stat):
    descriptor = None
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
        opened_stat = os.fstat(descriptor)
        if (
            (opened_stat.st_dev, opened_stat.st_ino)
            != (expected_stat.st_dev, expected_stat.st_ino)
            or not stat.S_ISREG(opened_stat.st_mode)
            or opened_stat.st_uid != os.getuid()
            or opened_stat.st_mode & 0o077
        ):
            raise SourceEvidenceError("credential file changed while opening")
        handle = os.fdopen(descriptor, "r", encoding="utf-8")
        descriptor = None
        with handle:
            return handle.read()
    except SourceEvidenceError:
        raise
    except (OSError, UnicodeDecodeError):
        raise SourceEvidenceError("credential file cannot be read safely") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _https_origin(url, *, origin_only=False):
    if not isinstance(url, str) or not url.strip():
        raise SourceEvidenceError("credential origin or request URL is invalid")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise SourceEvidenceError("credential origin or request URL is invalid") from None
    if parsed.username is not None or parsed.password is not None:
        raise SourceEvidenceError("URL userinfo is forbidden")
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise SourceEvidenceError("credential origin must use HTTPS")
    if origin_only and (
        parsed.path not in {""}
        or parsed.query
        or parsed.fragment
        or parsed.scheme != "https"
    ):
        raise SourceEvidenceError("credential origin must be an exact HTTPS origin")
    host = parsed.hostname.casefold()
    if ":" in host:
        host = f"[{host}]"
    netloc = host if port in {None, 443} else f"{host}:{port}"
    origin = f"https://{netloc}"
    if origin_only and url != origin:
        raise SourceEvidenceError("credential origin must be canonical and exact")
    return origin


def _contains_sensitive(value, sensitive_values):
    secrets = tuple(
        variant
        for secret in sensitive_values
        if isinstance(secret, str) and secret
        for variant in _bounded_percent_decoded_variants(secret)
    )
    if not secrets:
        return False
    if isinstance(value, dict):
        return any(
            _contains_sensitive(key, secrets) or _contains_sensitive(item, secrets)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set)):
        return any(_contains_sensitive(item, secrets) for item in value)
    if isinstance(value, bytes):
        rendered = value.decode("utf-8", errors="ignore")
    else:
        rendered = str(value)
    rendered_variants = _bounded_percent_decoded_variants(rendered)
    return any(
        secret in candidate
        for candidate in rendered_variants
        for secret in secrets
    )


def _bounded_percent_decoded_variants(value):
    variants = []
    current = str(value)
    for _ in range(3):
        folded = current.casefold()
        if folded not in variants:
            variants.append(folded)
        decoded = unquote(current, errors="replace")
        if decoded == current:
            break
        current = decoded
    return tuple(variants)


def _validated_request_url(url, *, sensitive_values=()):
    _https_origin(url)
    if _contains_sensitive(url, sensitive_values):
        raise SourceEvidenceError("request URL contains sensitive data")
    return url


def _sanitize_url_for_output(url, *, sensitive_values=()):
    _validated_request_url(url, sensitive_values=sensitive_values)
    parsed = urlsplit(url)
    origin = _https_origin(url)
    sanitized = origin + (parsed.path or "")
    if _contains_sensitive(sanitized, sensitive_values):
        raise SourceEvidenceError("request URL contains sensitive data")
    return sanitized


def _allowed_authorization_origins(route):
    route_spec = route["authoritative_retrieval_route"]
    route_kind = route_spec["kind"]
    origins = {_https_origin(route_spec["url"])}
    origins.update(_EXTRA_AUTHORIZATION_ORIGINS_BY_ROUTE_KIND.get(route_kind, set()))
    return origins


def _load_request_authorizations(
    path,
    *,
    selected_source_ids,
    route_by_id,
    cache_root,
):
    selected = set(selected_source_ids)
    unknown_selected = selected - set(route_by_id)
    if unknown_selected:
        raise SourceEvidenceError("credential selection contains an unknown source ID")
    restricted = {
        source_id
        for source_id in selected
        if route_by_id[source_id]["access_mode"] != "unattended"
    }
    if path is None:
        if restricted:
            missing = sorted(restricted)[0]
            raise SourceEvidenceError(
                f"credential authorization is required for source ID {missing}"
            )
        return {}

    candidate = Path(os.path.abspath(os.fspath(path)))
    repository_root = _nearest_repository_root(PROJECT_ROOT)
    cache_boundary = Path(cache_root).resolve(strict=False)
    if any(
        _path_is_within(candidate, boundary)
        for boundary in (repository_root, cache_boundary)
    ):
        raise SourceEvidenceError(
            "credential file must be outside the repository and cache roots"
        )
    try:
        file_stat = candidate.lstat()
    except OSError:
        raise SourceEvidenceError("credential file is unavailable") from None
    if stat.S_ISLNK(file_stat.st_mode):
        raise SourceEvidenceError("credential file must not be a symlink")
    if not stat.S_ISREG(file_stat.st_mode):
        raise SourceEvidenceError("credential file must be a regular file")
    if file_stat.st_uid != os.getuid():
        raise SourceEvidenceError("credential file owner must be the current user")
    if file_stat.st_mode & 0o077:
        raise SourceEvidenceError(
            "credential file permission bits must deny group and other access"
        )
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        raise SourceEvidenceError("credential file is unavailable") from None
    if any(
        _path_is_within(resolved, boundary)
        for boundary in (repository_root, cache_boundary)
    ):
        raise SourceEvidenceError(
            "credential file must be outside the repository and cache roots"
        )
    document = _json_without_duplicate_keys(
        _read_checked_credential_file(candidate, file_stat)
    )

    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "authorization_by_source_id",
    }:
        raise SourceEvidenceError("credential file has unsupported top-level fields")
    if (
        isinstance(document["schema_version"], bool)
        or document["schema_version"] != 1
    ):
        raise SourceEvidenceError("credential schema_version must equal 1")
    entries = document["authorization_by_source_id"]
    if not isinstance(entries, dict):
        raise SourceEvidenceError(
            "credential authorization_by_source_id must be a mapping"
        )
    entry_ids = set(entries)
    unknown_entries = entry_ids - set(route_by_id)
    if unknown_entries:
        raise SourceEvidenceError("credential file contains an unknown source ID")
    unselected = entry_ids - selected
    if unselected:
        raise SourceEvidenceError(
            "credential file contains authorization for an unselected source"
        )
    unattended = {
        source_id
        for source_id in entry_ids
        if route_by_id[source_id]["access_mode"] == "unattended"
    }
    if unattended:
        raise SourceEvidenceError(
            "credential file must not authorize an unattended source"
        )
    missing = restricted - entry_ids
    if missing:
        raise SourceEvidenceError(
            "credential authorization is missing for source ID "
            + sorted(missing)[0]
        )

    validated = {}
    for source_id in sorted(entry_ids):
        entry = entries[source_id]
        if not isinstance(entry, dict) or set(entry) != {
            "authorization_mode",
            "request_headers_by_origin",
        }:
            raise SourceEvidenceError(
                "credential authorization entry has unsupported fields"
            )
        mode = entry["authorization_mode"]
        if mode not in {"request_headers", "institution_network"}:
            raise SourceEvidenceError("credential authorization mode is invalid")
        route = route_by_id[source_id]
        origin_profiles = entry["request_headers_by_origin"]
        if not isinstance(origin_profiles, dict):
            raise SourceEvidenceError(
                "credential request_headers_by_origin must be a mapping"
            )
        if mode == "institution_network":
            if route["access_mode"] not in _INSTITUTION_NETWORK_ACCESS_MODES:
                raise SourceEvidenceError(
                    "credential authorization mode is incompatible with access mode"
                )
            if origin_profiles:
                raise SourceEvidenceError(
                    "institution-network authorization must not contain headers"
                )
            validated[source_id] = {
                "authorization_mode": mode,
                "request_headers_by_origin": {},
            }
            continue
        if not origin_profiles:
            raise SourceEvidenceError(
                "request-header authorization requires a nonempty origin map"
            )
        allowed_origins = _allowed_authorization_origins(route)
        validated_origins = {}
        for origin, headers in origin_profiles.items():
            normalized_origin = _https_origin(origin, origin_only=True)
            if normalized_origin not in allowed_origins:
                raise SourceEvidenceError(
                    "credential origin is not allowlisted for this source"
                )
            if not isinstance(headers, dict) or not headers:
                raise SourceEvidenceError(
                    "credential origin requires a nonempty header mapping"
                )
            seen_header_names = set()
            validated_headers = {}
            for header_name, header_value in headers.items():
                if not isinstance(header_name, str):
                    raise SourceEvidenceError("credential header name is invalid")
                folded = header_name.casefold()
                if folded in seen_header_names:
                    raise SourceEvidenceError(
                        "credential header names duplicate by case"
                    )
                seen_header_names.add(folded)
                if header_name not in _CREDENTIAL_HEADER_NAMES:
                    raise SourceEvidenceError(
                        "credential header is not in the closed allowlist"
                    )
                if (
                    not isinstance(header_value, str)
                    or not header_value.strip()
                    or "\r" in header_value
                    or "\n" in header_value
                ):
                    raise SourceEvidenceError("credential header value is invalid")
                validated_headers[header_name] = header_value
            validated_origins[normalized_origin] = validated_headers
        validated[source_id] = {
            "authorization_mode": mode,
            "request_headers_by_origin": validated_origins,
        }
    return validated


def _credential_headers_for_url(profile, url):
    if not profile or profile.get("authorization_mode") != "request_headers":
        return {}
    origin = _https_origin(url)
    return dict(profile["request_headers_by_origin"].get(origin, {}))


def _credential_values(profile):
    if not profile:
        return ()
    return tuple(
        value
        for headers in profile.get("request_headers_by_origin", {}).values()
        for value in headers.values()
    )


class _CredentialRedirectHandler(HTTPRedirectHandler):
    def __init__(self, credential_profile=None):
        super().__init__()
        self.credential_profile = credential_profile

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validated_request_url(
            newurl,
            sensitive_values=_credential_values(self.credential_profile),
        )
        redirected = super().redirect_request(
            req, fp, code, msg, headers, newurl
        )
        if redirected is None:
            return None
        for name, _ in list(redirected.header_items()):
            if name.casefold() in _CREDENTIAL_HEADER_NAMES_CASEFOLDED:
                redirected.remove_header(name)
        for name, value in _credential_headers_for_url(
            self.credential_profile, newurl
        ).items():
            redirected.add_unredirected_header(name, value)
        return redirected


def main(argv=None):
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--verify-offline", action="store_true")
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--ca-bundle", type=Path, default=DEFAULT_CA_BUNDLE)
    parser.add_argument("--request-credential-file", type=Path)
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
    if args.request_credential_file is not None and args.access_mode != "all":
        parser.error("--request-credential-file requires --access-mode all")
    if args.verify_offline:
        authorizations = {}
    elif args.access_mode == "all":
        try:
            authorizations = _load_request_authorizations(
                args.request_credential_file,
                selected_source_ids=selected_ids,
                route_by_id=route_by_id,
                cache_root=args.cache_root,
            )
        except SourceEvidenceError as exc:
            parser.error(str(exc))
    else:
        authorizations = {}

    outcomes = []
    for source_id in selected_ids:
        source = _plain(source_by_id[source_id])
        route = _plain(route_by_id[source_id])
        credential_profile = authorizations.get(source_id)
        sensitive_values = _credential_values(credential_profile)
        if route["access_mode"] != "unattended" and args.access_mode != "all":
            outcome = _outcome(
                source_id,
                "blocked",
                f"route requires {route['access_mode']}",
                sensitive_values=sensitive_values,
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
                credential_profile=credential_profile,
            )
        status = outcome.get("status")
        if status not in {"verified", "acquired", "resumed", "blocked", "failed"}:
            status = "failed"
            detail = "invalid internal acquisition outcome"
        else:
            detail = outcome.get("detail", "missing internal acquisition detail")
        outcome = _outcome(
            source_id,
            status,
            detail,
            sensitive_values=sensitive_values,
        )
        outcomes.append(outcome)
        print(json.dumps(outcome, sort_keys=True), flush=True)

    summary = {
        status: sum(item["status"] == status for item in outcomes)
        for status in sorted({item["status"] for item in outcomes})
    }
    print(json.dumps({"summary": summary, "total": len(outcomes)}, sort_keys=True))
    return 0 if all(item["status"] in {"verified", "acquired", "resumed", "blocked"} for item in outcomes) else 1


def _fetch_source(
    cache_root,
    source,
    route,
    *,
    ca_bundle,
    resume,
    credential_profile=None,
):
    source_id = source["source_id"]
    sensitive_values = _credential_values(credential_profile)
    source_dir = Path(cache_root) / source_id
    provenance_path = source_dir / "provenance.json"
    if source_dir.is_symlink():
        return _outcome(
            source_id,
            "failed",
            "cache directory is a symlink",
            sensitive_values=sensitive_values,
        )
    if source_dir.exists():
        if not resume:
            return _outcome(
                source_id,
                "failed",
                "cache directory already exists",
                sensitive_values=sensitive_values,
            )
        try:
            load_verified_source(
                source_dir,
                expected_source=source,
                provisioning_route=route,
            )
        except Exception as exc:
            return _outcome(
                source_id,
                "failed",
                f"existing cache is invalid: {exc}",
                sensitive_values=sensitive_values,
            )
        return _outcome(
            source_id,
            "resumed",
            "existing cache verified",
            sensitive_values=sensitive_values,
        )
    try:
        ssl_context = _ssl_context(ca_bundle)
        route_spec = {
            **route["authoritative_retrieval_route"],
            "expected_media_type": route["expected_media_type"],
            "access_mode": route["access_mode"],
        }
        response = _download(
            route_spec,
            ssl_context,
            credential_profile=credential_profile,
        )
        bibliographic = _fetch_bibliographic_metadata(source, ssl_context)
        evidence = _fetch_work_identity_evidence(
            source,
            route,
            ssl_context,
            bibliographic_metadata=bibliographic,
        )
        extension = payload_extension_for_media_type(route["expected_media_type"])
        payload_name = f"source.{extension}"
        provenance = _build_provenance(
            source,
            route,
            response,
            bibliographic,
            payload_name=payload_name,
            sensitive_values=sensitive_values,
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
        return _outcome(
            source_id,
            "acquired",
            response["final_url"],
            sensitive_values=sensitive_values,
        )
    except Exception as exc:
        return _outcome(
            source_id,
            "failed",
            f"new cache directory {source_dir} failed: {exc}",
            sensitive_values=sensitive_values,
        )


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


def _download(route, ssl_context, *, credential_profile=None):
    credential_values = _credential_values(credential_profile)
    request_url = _validated_request_url(
        route["url"], sensitive_values=credential_values
    )
    request = Request(
        request_url,
        headers={
            "Accept": route["expected_media_type"],
            "User-Agent": USER_AGENT,
        },
    )
    for name, value in _credential_headers_for_url(
        credential_profile, request_url
    ).items():
        request.add_unredirected_header(name, value)
    opener = build_opener(
        HTTPSHandler(context=ssl_context),
        _CredentialRedirectHandler(credential_profile),
    )
    try:
        with opener.open(request, timeout=60) as response:
            body = response.read()
            status = response.status
            headers = dict(response.headers.items())
            final_url_in_memory = response.geturl()
    except SourceEvidenceError:
        raise
    except Exception as exc:
        raise SourceEvidenceError(
            f"payload request failed for route kind {route.get('kind', 'unknown')}"
        ) from None
    final_url = _sanitize_url_for_output(
        final_url_in_memory,
        sensitive_values=credential_values,
    )
    if _contains_sensitive(body, credential_values):
        raise SourceEvidenceError("downloaded payload contains sensitive data")
    media_type = validate_download_response(
        route,
        status=status,
        headers=headers,
        body=body,
        final_url=final_url_in_memory,
    )
    safe_headers = {
        key: value
        for key, value in headers.items()
        if not _contains_sensitive(value, credential_values)
    }
    return {
        "body": body,
        "status": status,
        "headers": safe_headers,
        "final_url": final_url,
        "media_type": media_type,
    }


def _fetch_work_identity_evidence(
    source, route, ssl_context, *, bibliographic_metadata
):
    authoritative_route = route["authoritative_retrieval_route"]
    evidence_route = authoritative_route["work_identity_evidence"]
    if evidence_route["kind"] == "canonical_identity":
        return None
    media_type = (
        "text/html"
        if evidence_route["kind"] == "author_publications_same_work"
        else "application/json"
    )
    payload_name = (
        "work-identity.html" if media_type == "text/html" else "work-identity.json"
    )
    request_url = _validated_request_url(evidence_route["url"])
    request = Request(
        request_url,
        headers={"Accept": media_type, "User-Agent": USER_AGENT},
    )
    opener = build_opener(
        HTTPSHandler(context=ssl_context),
        _CredentialRedirectHandler(None),
    )
    with opener.open(request, timeout=30) as response:
        payload = response.read()
        payload_sha256 = hashlib.sha256(payload).hexdigest()
        payload_byte_length = len(payload)
        final_url_in_memory = _validated_request_url(response.geturl())
        if response.status != 200:
            raise SourceEvidenceError(
                f"work identity evidence returned HTTP status {response.status}"
            )
        normalized_response_headers = {
            str(key).casefold(): str(value)
            for key, value in response.headers.items()
        }
        response_content_type = normalized_response_headers.get(
            "content-type", ""
        ).split(";", 1)[0].strip().casefold()
    if response_content_type != media_type:
        raise SourceEvidenceError(
            "work identity evidence response media type mismatch"
        )
    if media_type == "application/json":
        try:
            document = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceEvidenceError(
                f"work identity evidence is invalid JSON: {exc}"
            ) from exc
    else:
        document = payload
    stable_route_url = _sanitize_url_for_output(request_url)
    document_base_url = _sanitize_url_for_output(final_url_in_memory)
    validation_route = {
        **authoritative_route,
        "work_identity_evidence": {
            **evidence_route,
            "url": document_base_url,
        },
    }
    validate_work_identity_document(
        document,
        identity=source["canonical_identity"],
        authoritative_route=validation_route,
        evidence_kind=evidence_route["kind"],
        bibliographic_metadata={
            **bibliographic_metadata,
            "doi": source["canonical_identity"].get("value", ""),
        },
    )
    return {
        "payload": payload,
        "descriptor": {
            "kind": evidence_route["kind"],
            "url": stable_route_url,
            "document_base_url": document_base_url,
            "media_type": media_type,
            "payload_relative_path": payload_name,
            "payload_sha256": payload_sha256,
            "payload_byte_length": payload_byte_length,
        },
    }

def _write_work_identity_sidecars(source_dir, evidence):
    if evidence is None:
        return
    payload_name = evidence["descriptor"]["payload_relative_path"]
    with source_dir.joinpath(payload_name).open("xb") as handle:
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


def _build_provenance(
    source,
    route,
    response,
    bibliographic,
    *,
    payload_name,
    sensitive_values=(),
):
    body = response["body"]
    identity = source["canonical_identity"]
    retrieval_kind = route["authoritative_retrieval_route"]["kind"]
    retrieval_route = route["authoritative_retrieval_route"]
    origin = authoritative_origin_for_route_kind(retrieval_kind)
    if response["media_type"] == "application/pdf":
        extraction = {
            "tool": "pdftotext",
            "version": _pdftotext_version(),
            "deterministic": True,
            "arguments": ["-layout", "-enc", "UTF-8"],
        }
    elif response["media_type"] == "application/xml":
        extraction = {
            "tool": "xml_text_content",
            "version": "python-stdlib",
            "deterministic": True,
        }
    elif response["media_type"] == "text/html":
        extraction = {
            "tool": "stdlib_html_visible_text",
            "version": 1,
            "deterministic": True,
            "arguments": [],
        }
    else:
        raise SourceEvidenceError("unsupported media type for provenance extraction")
    provenance = {
        "schema_version": 1,
        "source_id": source["source_id"],
        "source_identity": {
            "kind": identity["kind"],
            "value": identity["value"],
            "canonical_url": source["canonical_url"],
        },
        "bibliographic_metadata": bibliographic,
        "retrieval_metadata": {
            "url": _sanitize_url_for_output(
                response["final_url"],
                sensitive_values=sensitive_values,
            ),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "method": retrieval_kind,
            "authoritative_origin": origin,
            "http_status": response["status"],
            "response_headers": _stable_response_headers(
                response["headers"],
                forbidden_values=sensitive_values,
            ),
            "immutable_artifact_identifier": retrieval_route["artifact_identifier"],
            **(
                {
                    "work_identity_evidence": {
                        **retrieval_route["work_identity_evidence"],
                        "url": _sanitize_url_for_output(
                            retrieval_route["work_identity_evidence"]["url"],
                            sensitive_values=sensitive_values,
                        ),
                    }
                }
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
    if _contains_sensitive(provenance, sensitive_values):
        raise SourceEvidenceError("provenance contains sensitive data")
    return provenance


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


def _stable_response_headers(headers, *, forbidden_values=()):
    allowed = {"content-type", "content-length", "etag", "last-modified"}
    return {
        key.lower(): str(value)
        for key, value in headers.items()
        if key.lower() in allowed
        and not _contains_sensitive(value, forbidden_values)
    }


def _sanitize_detail(detail, *, sensitive_values=()):
    rendered = str(detail)
    if _contains_sensitive(rendered, sensitive_values):
        return "sensitive acquisition detail redacted"

    def sanitize_match(match):
        try:
            return _sanitize_url_for_output(
                match.group(0),
                sensitive_values=sensitive_values,
            )
        except SourceEvidenceError:
            return "[redacted-url]"

    sanitized = re.sub(
        r"https://[^\s\"'<>]+",
        sanitize_match,
        rendered,
        flags=re.IGNORECASE,
    )
    if _contains_sensitive(sanitized, sensitive_values):
        return "sensitive acquisition detail redacted"
    return sanitized


def _outcome(source_id, status, detail, *, sensitive_values=()):
    return {
        "source_id": source_id,
        "status": status,
        "detail": _sanitize_detail(detail, sensitive_values=sensitive_values),
    }


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
