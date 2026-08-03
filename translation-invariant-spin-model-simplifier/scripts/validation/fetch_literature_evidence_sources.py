"""Fetch or verify authoritative literature payloads with fail-closed routing."""

import argparse
from collections.abc import Mapping
import ctypes
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import stat
import sys
from urllib.parse import quote, unquote, urlencode, urlsplit
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
    _is_exact_oup_route,
    _load_json_bytes,
    _oup_crossref_bibliographic_metadata,
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
_HAL_GAREL_API_BASE = "https://api.archives-ouvertes.fr/search/"
_HAL_GAREL_STABLE_RECORD_ID = "hal-02340631v1"
_HAL_GAREL_STABLE_DOCUMENT_URL = "https://hal.science/hal-02340631v1"
_HAL_GAREL_QUERY_PAIRS = (
    ("q", "halId_s:hal-02340631 AND version_i:1"),
    (
        "fl",
        "docid,linkExtId_s,linkExtUrl_s,title_s,journalTitle_s,"
        "authFullName_s,halId_s,uri_s,version_i,submitType_s,docType_s,"
        "issue_s,page_s,volume_s,doiId_s,producedDateY_i,publicationDate_s",
    ),
    ("rows", "1"),
    ("start", "0"),
    ("wt", "json"),
)
_CORE_MG_DOI = "10.1088/0305-4470/17/13/020"
_CORE_MG_INITIAL_URL = "https://core.ac.uk/download/572184419.pdf"
_CORE_MG_SECOND_URL = (
    "https://fileserver-az.core.ac.uk/download/572184419.pdf"
)
_CORE_MG_FINAL_URL = (
    "https://pdf.core.ac.uk/corefilesystem/pdf/363/572184419.pdf"
)
_CORE_MG_OUTPUT_URL = "https://api.core.ac.uk/v3/outputs/572184419"
_RENAME_NOREPLACE = 1
_CREDENTIAL_HEADER_NAMES = {
    "Cookie",
    "Authorization",
    "X-ELS-APIKey",
    "X-ELS-Insttoken",
}
_CREDENTIAL_HEADER_NAMES_CASEFOLDED = {
    name.casefold() for name in _CREDENTIAL_HEADER_NAMES
}
_MAX_SENSITIVE_URL_QUERY_CHARACTERS = 16 * 1024
_SENSITIVE_QUERY_NORMALIZATION_WORK_MULTIPLIER = 4
_HEXADECIMAL_CHARACTERS = frozenset("0123456789abcdefABCDEF")
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


def _sensitive_query_percent_forest(query):
    """Build every ASCII percent-decoding pass without repeatedly decoding."""
    roots = []
    maximum_stage = 0
    for character in query:
        roots.append((character, 0, ()))
        if character == "+":
            maximum_stage = max(maximum_stage, 1)

        while (
            len(roots) >= 3
            and roots[-3][0] == "%"
            and roots[-2][0] in _HEXADECIMAL_CHARACTERS
            and roots[-1][0] in _HEXADECIMAL_CHARACTERS
        ):
            children = tuple(roots[-3:])
            byte_value = int(children[1][0] + children[2][0], 16)
            if byte_value >= 0x80:
                return None, None
            del roots[-3:]
            birth_stage = max(child[1] for child in children) + 1
            decoded = chr(byte_value)
            roots.append((decoded, birth_stage, children))
            visible_through_stage = birth_stage
            if decoded == "+":
                visible_through_stage += 1
            maximum_stage = max(maximum_stage, visible_through_stage)
    return tuple(roots), maximum_stage


def _sensitive_query_frontier(
    roots,
    stage,
    *,
    remaining_work,
):
    """Render one synchronous form-decoding stage from an immutable forest."""
    pending = list(reversed(roots))
    characters = []
    work = 0
    while pending:
        work += 1
        if work > remaining_work:
            return None, work
        character, birth_stage, children = pending.pop()
        if children and birth_stage > stage:
            pending.extend(reversed(children))
            continue
        if character == "+" and stage > birth_stage:
            character = " "
        characters.append(character)
    return "".join(characters), work


def _query_form_frontier_contains_sensitive(query, secrets):
    roots, maximum_stage = _sensitive_query_percent_forest(query)
    if roots is None:
        return True

    remaining_work = (
        len(query) * _SENSITIVE_QUERY_NORMALIZATION_WORK_MULTIPLIER
    )
    for stage in range(maximum_stage + 1):
        # Expanded encodings have geometrically shrinking frontiers. Compact
        # adversarial nesting exhausts this linear budget and fails closed.
        frontier, work = _sensitive_query_frontier(
            roots,
            stage,
            remaining_work=remaining_work,
        )
        if frontier is None:
            return True
        remaining_work -= work
        folded = frontier.casefold()
        if any(secret in folded for secret in secrets):
            return True
    return False


def _request_url_contains_sensitive(url, sensitive_values):
    active_sensitive_values = tuple(
        secret
        for secret in sensitive_values
        if isinstance(secret, str) and secret
    )
    secrets = tuple(
        variant
        for secret in active_sensitive_values
        for variant in _bounded_percent_decoded_variants(secret)
    )
    if not secrets:
        return False

    query = urlsplit(url).query
    if len(query) > _MAX_SENSITIVE_URL_QUERY_CHARACTERS:
        return True
    if _contains_sensitive(url, active_sensitive_values):
        return True
    return _query_form_frontier_contains_sensitive(query, secrets)


def _validated_request_url(url, *, sensitive_values=()):
    _https_origin(url)
    if _request_url_contains_sensitive(url, sensitive_values):
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


def _url_query_sensitive_values(url):
    try:
        query = urlsplit(url).query
    except ValueError:
        return ()
    if not query:
        return ()
    values = [query]
    for component in query.split("&"):
        values.append(component)
        if "=" in component:
            _name, value = component.split("=", 1)
            values.append(value)
            values.append(unquote(value).replace("+", " "))
    return tuple(dict.fromkeys(value for value in values if value))


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


def _is_exact_core_fulltext_route(route):
    evidence = route.get("work_identity_evidence")
    return (
        route.get("kind") == "institutional_repository_pdf"
        and route.get("url") == _CORE_MG_INITIAL_URL
        and route.get("expected_media_type") == "application/pdf"
        and route.get("artifact_identifier") == "core:572184419"
        and isinstance(evidence, Mapping)
        and evidence.get("kind") == "core_same_work_output"
        and evidence.get("url") == _CORE_MG_OUTPUT_URL
    )


class _CoreFullTextRedirectHandler(_CredentialRedirectHandler):
    def __init__(self, credential_profile=None):
        super().__init__(credential_profile)
        self._validated_redirects = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if _credential_values(self.credential_profile) or any(
            name.casefold() in _CREDENTIAL_HEADER_NAMES_CASEFOLDED
            for name, _ in req.header_items()
        ):
            raise SourceEvidenceError(
                "CORE redirect rejects credential-bearing request headers"
            )

        current_url = req.full_url
        if self._validated_redirects == 0:
            if current_url != _CORE_MG_INITIAL_URL:
                raise SourceEvidenceError(
                    "CORE first redirect source is not approved"
                )
            if newurl != _CORE_MG_SECOND_URL:
                raise SourceEvidenceError(
                    "CORE first redirect target is not approved"
                )
        elif self._validated_redirects == 1:
            if current_url != _CORE_MG_SECOND_URL:
                raise SourceEvidenceError(
                    "CORE final redirect source is not approved"
                )
            try:
                parsed = urlsplit(newurl)
                query_free = _sanitize_url_for_output(newurl)
            except SourceEvidenceError:
                raise
            if parsed.fragment:
                raise SourceEvidenceError(
                    "CORE final redirect fragment is forbidden"
                )
            if len(parsed.query) > _MAX_SENSITIVE_URL_QUERY_CHARACTERS:
                raise SourceEvidenceError(
                    "CORE final redirect query exceeds the safe limit"
                )
            if query_free != _CORE_MG_FINAL_URL:
                raise SourceEvidenceError(
                    "CORE final redirect target is not approved"
                )
        else:
            raise SourceEvidenceError(
                "CORE redirect depth exceeds the exact two-hop policy"
            )

        redirected = super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            newurl,
        )
        if redirected is not None:
            self._validated_redirects += 1
        return redirected

    def require_complete_response(self, final_url):
        if self._validated_redirects != 2:
            raise SourceEvidenceError(
                "CORE response requires exactly two approved redirects"
            )
        parsed = urlsplit(final_url)
        if parsed.fragment:
            raise SourceEvidenceError(
                "CORE final response fragment is forbidden"
            )
        if len(parsed.query) > _MAX_SENSITIVE_URL_QUERY_CHARACTERS:
            raise SourceEvidenceError(
                "CORE final response query exceeds the safe limit"
            )
        if _sanitize_url_for_output(final_url) != _CORE_MG_FINAL_URL:
            raise SourceEvidenceError(
                "CORE final response URL is not approved"
            )


class _CoreDownloadResponse(dict):
    """Keep raw CORE bytes available internally but outside serialization."""

    def __init__(self, *, body, **safe_fields):
        super().__init__(safe_fields)
        self._body = body

    def __getitem__(self, key):
        if key == "body":
            return self._body
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key == "body":
            return self._body
        return super().get(key, default)

    def __contains__(self, key):
        return key == "body" or super().__contains__(key)


class _HALNoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SourceEvidenceError(
            "HAL work identity evidence redirect rejected"
        )


class _CoreOutputNoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SourceEvidenceError(
            "CORE work identity evidence redirect rejected"
        )


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
    cache_root = Path(os.path.abspath(os.fspath(cache_root)))
    source_dir = cache_root / source_id
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
        identity = source.get("canonical_identity", {})
        exact_core_route = (
            identity.get("kind") == "doi"
            and str(identity.get("value", "")).casefold() == _CORE_MG_DOI
            and _is_exact_core_fulltext_route(route_spec)
        )
        exact_oup_route = _is_exact_oup_route(
            identity,
            route_spec,
            source_id=source_id,
        )
        if exact_oup_route:
            evidence = _fetch_work_identity_evidence(
                source,
                route,
                ssl_context,
                bibliographic_metadata=None,
            )
            bibliographic = evidence["bibliographic_metadata"]
            response = _download(
                route_spec,
                ssl_context,
                credential_profile=credential_profile,
            )
        elif exact_core_route:
            bibliographic = _fetch_bibliographic_metadata(source, ssl_context)
            evidence = _fetch_work_identity_evidence(
                source,
                route,
                ssl_context,
                bibliographic_metadata=bibliographic,
            )
            response = _download(
                route_spec,
                ssl_context,
                credential_profile=credential_profile,
            )
        else:
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
        provenance_payload = _serialized_json_bytes(provenance)
        _install_verified_cache_candidate(
            cache_root,
            source_dir,
            source=source,
            route=route,
            payload_name=payload_name,
            payload=response["body"],
            provenance_payload=provenance_payload,
            evidence=evidence,
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


def _serialized_json_bytes(document):
    rendered = json.dumps(
        document,
        indent=2,
        sort_keys=True,
        ensure_ascii=True,
    )
    return (rendered + "\n").encode("utf-8")


class _AnchoredStagingPath:
    def __init__(self, path, directory_fd):
        self.path = Path(path)
        self.directory_fd = directory_fd

    def __fspath__(self):
        return os.fspath(self.path)


class _OwnedStagingDirectory:
    def __init__(
        self,
        *,
        cache_root,
        root_fd,
        root_identity,
        name,
        staging_fd,
        staging_identity,
    ):
        self.cache_root = Path(cache_root)
        self.root_fd = root_fd
        self.root_identity = root_identity
        self.name = name
        self.path = self.cache_root / name
        self.staging_fd = staging_fd
        self.staging_identity = staging_identity
        self.owned = True

    def __fspath__(self):
        return os.fspath(self.path)

    def destination(self, name):
        return _AnchoredStagingPath(self.path / name, self.staging_fd)

    def close(self):
        close_errors = []
        for attribute in ("staging_fd", "root_fd"):
            descriptor = getattr(self, attribute)
            if descriptor is not None:
                setattr(self, attribute, None)
                try:
                    os.close(descriptor)
                except BaseException as error:
                    close_errors.append(error)
        _raise_cleanup_errors(
            "multiple staging directory descriptor close failures",
            close_errors,
        )


def _exclusive_write_bytes(path, payload):
    directory_fd = getattr(path, "directory_fd", None)
    if directory_fd is None:
        with Path(path).open("xb") as handle:
            handle.write(payload)
        return
    descriptor = os.open(
        Path(path).name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
        0o666,
        dir_fd=directory_fd,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(payload)
    finally:
        os.close(descriptor)


def _directory_identity(status):
    return status.st_dev, status.st_ino


def _require_real_directory(status, message):
    if not stat.S_ISDIR(status.st_mode) or stat.S_ISLNK(status.st_mode):
        raise SourceEvidenceError(message)


def _raise_cleanup_errors(message, errors):
    retained = []
    for error in errors:
        if error is not None and not any(error is item for item in retained):
            retained.append(error)
    if not retained:
        return
    if len(retained) == 1:
        raise retained[0]
    aggregate = SourceEvidenceError(message)
    aggregate.cache_cleanup_errors = tuple(retained)
    raise aggregate


def _revalidate_cache_root_binding(cache_root, root_fd, root_identity):
    descriptor_status = os.fstat(root_fd)
    _require_real_directory(
        descriptor_status,
        "source cache root directory descriptor changed",
    )
    if _directory_identity(descriptor_status) != root_identity:
        raise SourceEvidenceError(
            "source cache root directory descriptor changed"
        )
    try:
        path_status = os.stat(cache_root, follow_symlinks=False)
    except OSError as exc:
        raise SourceEvidenceError(
            f"source cache root pathname changed: {exc}"
        ) from exc
    _require_real_directory(
        path_status,
        "source cache root pathname changed",
    )
    if _directory_identity(path_status) != root_identity:
        raise SourceEvidenceError("source cache root pathname changed")


def _revalidate_cache_root(staging):
    _revalidate_cache_root_binding(
        staging.cache_root,
        staging.root_fd,
        staging.root_identity,
    )


def _revalidate_owned_staging_directory(staging):
    _revalidate_cache_root(staging)
    descriptor_status = os.fstat(staging.staging_fd)
    _require_real_directory(
        descriptor_status,
        "invocation-owned staging directory changed",
    )
    if _directory_identity(descriptor_status) != staging.staging_identity:
        raise SourceEvidenceError(
            "invocation-owned staging directory changed"
        )
    try:
        name_status = os.stat(
            staging.name,
            dir_fd=staging.root_fd,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise SourceEvidenceError(
            f"invocation-owned staging directory changed: {exc}"
        ) from exc
    _require_real_directory(
        name_status,
        "invocation-owned staging directory changed",
    )
    if _directory_identity(name_status) != staging.staging_identity:
        raise SourceEvidenceError(
            "invocation-owned staging directory changed"
        )


def _remove_directory_contents_fd(directory_fd):
    with os.scandir(directory_fd) as entries:
        names = [
            (
                entry.name,
                entry.stat(follow_symlinks=False),
            )
            for entry in entries
        ]
    for name, observed_status in names:
        if not stat.S_ISDIR(observed_status.st_mode) or stat.S_ISLNK(
            observed_status.st_mode
        ):
            os.unlink(name, dir_fd=directory_fd)
            continue
        child_fd = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=directory_fd,
        )
        try:
            child_status = os.fstat(child_fd)
            _require_real_directory(
                child_status,
                "invocation-owned staging child changed before cleanup",
            )
            child_identity = _directory_identity(child_status)
            if child_identity != _directory_identity(observed_status):
                raise SourceEvidenceError(
                    "invocation-owned staging child changed before cleanup"
                )
            _remove_directory_contents_fd(child_fd)
            child_status = os.stat(
                name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISDIR(child_status.st_mode)
                or stat.S_ISLNK(child_status.st_mode)
                or _directory_identity(child_status) != child_identity
            ):
                raise SourceEvidenceError(
                    "invocation-owned staging child changed before cleanup"
                )
            os.rmdir(name, dir_fd=directory_fd)
        finally:
            os.close(child_fd)


def _remove_preowner_staging_directory(
    *,
    cache_root,
    root_fd,
    root_identity,
    name,
    expected_identity,
    staging_fd,
):
    cleanup_fd = staging_fd
    close_cleanup_fd = False
    cleanup_error = None
    try:
        _revalidate_cache_root_binding(cache_root, root_fd, root_identity)
        if cleanup_fd is None:
            cleanup_fd = os.open(
                name,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
                dir_fd=root_fd,
            )
            close_cleanup_fd = True
        descriptor_status = os.fstat(cleanup_fd)
        _require_real_directory(
            descriptor_status,
            "new staging directory changed before allocation cleanup",
        )
        descriptor_identity = _directory_identity(descriptor_status)
        if (
            expected_identity is not None
            and descriptor_identity != expected_identity
        ):
            raise SourceEvidenceError(
                "new staging directory changed before allocation cleanup"
            )
        name_status = os.stat(
            name,
            dir_fd=root_fd,
            follow_symlinks=False,
        )
        _require_real_directory(
            name_status,
            "new staging directory changed before allocation cleanup",
        )
        if _directory_identity(name_status) != descriptor_identity:
            raise SourceEvidenceError(
                "new staging directory changed before allocation cleanup"
            )
        with os.scandir(cleanup_fd) as entries:
            if next(entries, None) is not None:
                raise SourceEvidenceError(
                    "new staging directory is not empty during allocation cleanup"
                )
        os.rmdir(name, dir_fd=root_fd)
    except BaseException as error:
        cleanup_error = error
    finally:
        if close_cleanup_fd and cleanup_fd is not None:
            try:
                os.close(cleanup_fd)
            except BaseException as error:
                if cleanup_error is None:
                    cleanup_error = error
                else:
                    _attach_cleanup_error(cleanup_error, error)
    if cleanup_error is not None:
        raise cleanup_error


def _owned_staging_directory(cache_root):
    cache_root = Path(cache_root)
    if os.path.lexists(cache_root):
        root_status = cache_root.lstat()
        if not stat.S_ISDIR(root_status.st_mode) or stat.S_ISLNK(
            root_status.st_mode
        ):
            raise SourceEvidenceError(
                "source cache root must be a real directory"
            )
    else:
        cache_root.mkdir(parents=True, exist_ok=False)
    root_fd = None
    staging_fd = None
    staging = None
    created_name = None
    created_identity = None
    try:
        root_fd = os.open(
            cache_root,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        descriptor_status = os.fstat(root_fd)
        _require_real_directory(
            descriptor_status,
            "source cache root must be a real directory",
        )
        root_identity = _directory_identity(descriptor_status)
        path_status = os.stat(cache_root, follow_symlinks=False)
        _require_real_directory(
            path_status,
            "source cache root must be a real directory",
        )
        if _directory_identity(path_status) != root_identity:
            raise SourceEvidenceError("source cache root pathname changed")
        for _attempt in range(128):
            name = ".literature-evidence-staging-" + secrets.token_hex(16)
            try:
                os.mkdir(name, mode=0o700, dir_fd=root_fd)
            except FileExistsError:
                continue
            created_name = name
            break
        else:
            raise SourceEvidenceError(
                "could not allocate invocation-owned staging directory"
            )
        created_status = os.stat(
            created_name,
            dir_fd=root_fd,
            follow_symlinks=False,
        )
        _require_real_directory(
            created_status,
            "new staging directory changed during allocation",
        )
        created_identity = _directory_identity(created_status)
        staging_fd = os.open(
            created_name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=root_fd,
        )
        staging_status = os.fstat(staging_fd)
        _require_real_directory(
            staging_status,
            "new staging directory changed during allocation",
        )
        staging_identity = _directory_identity(staging_status)
        if staging_identity != created_identity:
            raise SourceEvidenceError(
                "new staging directory changed during allocation"
            )
        staging = _OwnedStagingDirectory(
            cache_root=cache_root,
            root_fd=root_fd,
            root_identity=root_identity,
            name=created_name,
            staging_fd=staging_fd,
            staging_identity=staging_identity,
        )
        _revalidate_owned_staging_directory(staging)
        return staging
    except BaseException as primary_error:
        cleanup_errors = []
        if staging is not None:
            try:
                _remove_owned_staging_directory(staging)
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
            try:
                staging.close()
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
        else:
            if created_name is not None:
                try:
                    _remove_preowner_staging_directory(
                        cache_root=cache_root,
                        root_fd=root_fd,
                        root_identity=root_identity,
                        name=created_name,
                        expected_identity=created_identity,
                        staging_fd=staging_fd,
                    )
                except BaseException as cleanup_error:
                    cleanup_errors.append(cleanup_error)
            for descriptor in (staging_fd, root_fd):
                if descriptor is None:
                    continue
                try:
                    os.close(descriptor)
                except BaseException as cleanup_error:
                    cleanup_errors.append(cleanup_error)
        for cleanup_error in cleanup_errors:
            _attach_cleanup_error(primary_error, cleanup_error)
        raise


def _remove_owned_staging_directory(staging, directory_identity=None):
    if not staging.owned:
        return
    _revalidate_owned_staging_directory(staging)
    _remove_directory_contents_fd(staging.staging_fd)
    _revalidate_owned_staging_directory(staging)
    os.rmdir(staging.name, dir_fd=staging.root_fd)
    staging.owned = False


def _publish_directory_noreplace(staging, target):
    if sys.platform != "linux":
        raise SourceEvidenceError(
            "atomic no-replace cache publication requires Linux"
        )
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    target = Path(target)
    if target.parent != staging.cache_root or target.name in {"", ".", ".."}:
        raise SourceEvidenceError("cache publication target is invalid")
    arguments = (
        staging.root_fd,
        os.fsencode(staging.name),
        staging.root_fd,
        os.fsencode(target.name),
        _RENAME_NOREPLACE,
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
        _revalidate_owned_staging_directory(staging)
        ctypes.set_errno(0)
        result = renameat2(*arguments)
    else:
        syscall_number = {
            "x86_64": 316,
            "aarch64": 276,
        }.get(os.uname().machine)
        syscall = getattr(libc, "syscall", None)
        if syscall_number is None or syscall is None:
            raise SourceEvidenceError(
                "Linux renameat2 no-replace publication is unavailable"
            )
        syscall.restype = ctypes.c_long
        _revalidate_owned_staging_directory(staging)
        ctypes.set_errno(0)
        result = syscall(syscall_number, *arguments)
    if result == 0:
        staging.owned = False
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise SourceEvidenceError("cache directory already exists")
    raise SourceEvidenceError(
        "atomic no-replace cache publication failed: "
        + os.strerror(error_number)
    )


def _install_verified_cache_candidate(
    cache_root,
    source_dir,
    *,
    source,
    route,
    payload_name,
    payload,
    provenance_payload,
    evidence,
):
    staging = None
    primary_error = None
    try:
        staging = _owned_staging_directory(cache_root)
        _exclusive_write_bytes(staging.destination(payload_name), payload)
        _exclusive_write_bytes(
            staging.destination("provenance.json"),
            provenance_payload,
        )
        if evidence is not None:
            _exclusive_write_bytes(
                staging.destination(
                    evidence["descriptor"]["payload_relative_path"]
                ),
                evidence["payload"],
            )
            _exclusive_write_bytes(
                staging.destination("work-identity.provenance.json"),
                _serialized_json_bytes(evidence["descriptor"]),
            )
        _revalidate_owned_staging_directory(staging)
        load_verified_source(
            staging.path,
            expected_source=source,
            provisioning_route=route,
        )
        _revalidate_owned_staging_directory(staging)
        _publish_directory_noreplace(staging, source_dir)
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        if staging is not None:
            cleanup_errors = []
            published = primary_error is None and not staging.owned
            try:
                if staging.owned:
                    _remove_owned_staging_directory(staging)
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
            try:
                staging.close()
            except BaseException as cleanup_error:
                cleanup_errors.append(cleanup_error)
            if primary_error is not None:
                for cleanup_error in cleanup_errors:
                    _attach_cleanup_error(primary_error, cleanup_error)
            elif cleanup_errors and not published:
                _raise_cleanup_errors(
                    "multiple staging candidate cleanup failures",
                    cleanup_errors,
                )


def _exception_identity_graph(error):
    pending = [error]
    seen = set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        pending.extend((current.__cause__, current.__context__))
        pending.extend(getattr(current, "cache_cleanup_errors", ()))
    return seen


def _attach_cleanup_error(primary_error, cleanup_error):
    if id(cleanup_error) in _exception_identity_graph(primary_error):
        return
    retained = list(getattr(primary_error, "cache_cleanup_errors", ()))
    if not any(error is cleanup_error for error in retained):
        retained.append(cleanup_error)
    primary_error.cache_cleanup_errors = tuple(retained)


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
    exact_core_route = _is_exact_core_fulltext_route(route)
    if exact_core_route and credential_values:
        raise SourceEvidenceError(
            "CORE full-text route rejects credential-bearing requests"
        )
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
    redirect_handler = (
        _CoreFullTextRedirectHandler(credential_profile)
        if exact_core_route
        else _CredentialRedirectHandler(credential_profile)
    )
    opener = build_opener(
        HTTPSHandler(context=ssl_context),
        redirect_handler,
    )
    try:
        with opener.open(request, timeout=60) as response:
            final_url_in_memory = response.geturl()
            if exact_core_route:
                redirect_handler.require_complete_response(final_url_in_memory)
            body = response.read()
            status = response.status
            headers = dict(response.headers.items())
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
    query_sensitive_values = (
        _url_query_sensitive_values(final_url_in_memory)
        if exact_core_route
        else ()
    )
    response_sensitive_values = tuple(
        dict.fromkeys((*credential_values, *query_sensitive_values))
    )
    if _contains_sensitive(body, response_sensitive_values):
        raise SourceEvidenceError("downloaded payload contains sensitive data")
    core_validation_error = None
    try:
        media_type = validate_download_response(
            route,
            status=status,
            headers=headers,
            body=body,
            final_url=final_url_in_memory,
        )
    except SourceEvidenceError as exc:
        sanitized_detail = _sanitize_detail(
            exc,
            sensitive_values=response_sensitive_values,
        )
        if exact_core_route:
            if _contains_sensitive(exc, response_sensitive_values):
                sanitized_detail = (
                    "CORE media validation failed after signed-final receipt; "
                    "sensitive query detail redacted"
                )
            core_validation_error = SourceEvidenceError(sanitized_detail)
        else:
            exc.args = (sanitized_detail,)
            exc.__cause__ = None
            exc.__context__ = None
            raise
    if core_validation_error is not None:
        raise core_validation_error from None
    safe_headers = {}
    for key, value in headers.items():
        if _contains_sensitive(key, response_sensitive_values):
            raise SourceEvidenceError(
                "response header name contains sensitive data"
            )
        if not _contains_sensitive(value, response_sensitive_values):
            safe_headers[key] = value
    safe_response_fields = {
        "status": status,
        "headers": safe_headers,
        "final_url": final_url,
        "media_type": media_type,
    }
    if exact_core_route:
        response_mapping = _CoreDownloadResponse(
            body=body,
            **safe_response_fields,
        )
    else:
        response_mapping = {
            "body": body,
            **safe_response_fields,
        }
    if _contains_sensitive(response_mapping, response_sensitive_values):
        raise SourceEvidenceError("download response contains sensitive data")
    return response_mapping


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
    stable_route_url = _validated_request_url(evidence_route["url"])
    exact_core_evidence = (
        evidence_route["kind"] == "core_same_work_output"
        and stable_route_url == _CORE_MG_OUTPUT_URL
        and _is_exact_core_fulltext_route(authoritative_route)
    )
    if evidence_route["kind"] == "hal_same_work_bibliographic_payload":
        if (
            stable_route_url != _HAL_GAREL_API_BASE
            or evidence_route.get("record_identifier")
            != _HAL_GAREL_STABLE_RECORD_ID
            or evidence_route.get("stable_document_url")
            != _HAL_GAREL_STABLE_DOCUMENT_URL
        ):
            raise SourceEvidenceError("Garel HAL evidence route is invalid")
        request_url = stable_route_url + "?" + urlencode(
            _HAL_GAREL_QUERY_PAIRS
        )
    else:
        request_url = stable_route_url
    request = Request(
        request_url,
        headers={"Accept": media_type, "User-Agent": USER_AGENT},
    )
    if evidence_route["kind"] == "hal_same_work_bibliographic_payload":
        redirect_handler = _HALNoRedirectHandler()
    elif exact_core_evidence:
        redirect_handler = _CoreOutputNoRedirectHandler()
    else:
        redirect_handler = _CredentialRedirectHandler(None)
    opener = build_opener(
        HTTPSHandler(context=ssl_context),
        redirect_handler,
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
        document = _load_json_bytes(
            payload,
            context="work identity evidence JSON",
        )
    else:
        document = payload
    exact_oup_evidence = evidence_route["kind"] == "crossref_oup_same_work"
    if exact_oup_evidence:
        if not _is_exact_oup_route(
            source.get("canonical_identity"),
            authoritative_route,
            source_id=source.get("source_id"),
        ):
            raise SourceEvidenceError("OUP Crossref evidence route is invalid")
        if final_url_in_memory != request_url:
            raise SourceEvidenceError(
                "OUP Crossref work identity evidence redirected unexpectedly"
            )
        bibliographic_metadata = _oup_crossref_bibliographic_metadata(
            document
        )
        stable_route_url = _sanitize_url_for_output(request_url)
        document_base_url = stable_route_url
    elif evidence_route["kind"] == "hal_same_work_bibliographic_payload":
        if final_url_in_memory != request_url:
            raise SourceEvidenceError(
                "HAL work identity evidence redirected unexpectedly"
            )
        document_base_url = _HAL_GAREL_STABLE_DOCUMENT_URL
    elif exact_core_evidence:
        if final_url_in_memory != request_url:
            raise SourceEvidenceError(
                "CORE work identity evidence redirected unexpectedly"
            )
        stable_route_url = _sanitize_url_for_output(request_url)
        document_base_url = stable_route_url
    else:
        stable_route_url = _sanitize_url_for_output(request_url)
        document_base_url = _sanitize_url_for_output(final_url_in_memory)
    validation_route = {
        **authoritative_route,
        "work_identity_evidence": {
            **evidence_route,
            "url": (
                stable_route_url
                if evidence_route["kind"]
                == "hal_same_work_bibliographic_payload"
                else document_base_url
            ),
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
    result = {
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
    if exact_oup_evidence:
        result["bibliographic_metadata"] = bibliographic_metadata
    return result


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
    exact_garel = doi.casefold() == "10.1088/0305-4470/16/10/023"
    exact_core = doi.casefold() == _CORE_MG_DOI
    url = f"https://api.crossref.org/works/{quote(doi, safe='')}"
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, context=ssl_context, timeout=30) as response:
        document = _load_json_bytes(
            response.read(),
            context="Crossref metadata JSON",
        )
    message = document.get("message", {})
    if str(message.get("DOI", "")).lower() != doi.lower():
        raise SourceEvidenceError("Crossref DOI metadata disagrees with source identity")
    title = _first_text(message.get("title"), "Crossref title")
    venue = _first_text(message.get("container-title"), "Crossref venue")
    raw_authors = message.get("author", [])
    exact_author_count = 2 if exact_garel else 3 if exact_core else None
    if exact_author_count is not None:
        if (
            not isinstance(raw_authors, list)
            or len(raw_authors) != exact_author_count
        ):
            raise SourceEvidenceError(
                "Crossref raw authors have incorrect cardinality"
            )
        for author in raw_authors:
            if not isinstance(author, dict):
                raise SourceEvidenceError(
                    "Crossref raw authors contain a non-mapping entry"
                )
            for field in ("given", "family"):
                value = author.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise SourceEvidenceError(
                        f"Crossref raw authors contain invalid {field}"
                    )
    authors = []
    for author in raw_authors:
        rendered = " ".join(
            part for part in (author.get("given", ""), author.get("family", "")) if part
        ).strip()
        if rendered:
            authors.append(rendered)
    if not authors:
        raise SourceEvidenceError("Crossref metadata has no authors")
    publication_date = _crossref_date(message)
    metadata = {
        "title": title,
        "authors": authors,
        "venue": venue,
        "publication_date": publication_date,
    }
    if exact_garel:
        metadata.update(
            {
                "doi": str(message.get("DOI", "")),
                "volume": str(message.get("volume", "")),
                "issue": str(message.get("issue", "")),
                "pages": str(message.get("page", "")),
            }
        )
    return metadata


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
        descriptor_version = (
            2
            if _is_exact_oup_route(
                identity,
                retrieval_route,
                source_id=source.get("source_id"),
            )
            else 1
        )
        extraction = {
            "tool": "stdlib_html_visible_text",
            "version": descriptor_version,
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


def _query_echo_secret_is_distinctive(value):
    if "=" in value or "&" in value:
        return True
    decoded = unquote(value).replace("+", " ")
    return (
        len(decoded) >= 8
        and any(character.isalpha() for character in decoded)
        and all(character.isprintable() for character in decoded)
    )


def _redact_standalone_query_echo(rendered, secret):
    prefix = r"(?<![a-z0-9])" if secret[0].isalnum() else ""
    suffix = r"(?![a-z0-9])" if secret[-1].isalnum() else ""
    return re.sub(
        prefix + re.escape(secret) + suffix,
        "[redacted-query]",
        rendered,
        flags=re.IGNORECASE,
    )


def _sanitize_detail(detail, *, sensitive_values=()):
    rendered = str(detail)
    if _contains_sensitive(rendered, sensitive_values):
        return "sensitive acquisition detail redacted"

    trailing_url_punctuation = ".,;:!?)]}"
    query_secrets = []
    for match in re.finditer(
        r"https://[^\s\"'<>]+",
        rendered,
        flags=re.IGNORECASE,
    ):
        candidate = match.group(0).rstrip(trailing_url_punctuation)
        query_secrets.extend(_url_query_sensitive_values(candidate))

    def sanitize_match(match):
        matched = match.group(0)
        candidate = matched.rstrip(trailing_url_punctuation)
        suffix = matched[len(candidate) :]
        try:
            return _sanitize_url_for_output(
                candidate,
                sensitive_values=sensitive_values,
            ) + suffix
        except SourceEvidenceError:
            return "[redacted-url]"

    sanitized = re.sub(
        r"https://[^\s\"'<>]+",
        sanitize_match,
        rendered,
        flags=re.IGNORECASE,
    )
    for secret in sorted(
        {
            variant
            for value in query_secrets
            if value
            for variant in _bounded_percent_decoded_variants(value)
            if variant and _query_echo_secret_is_distinctive(variant)
        },
        key=len,
        reverse=True,
    ):
        sanitized = _redact_standalone_query_echo(
            sanitized,
            secret,
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
