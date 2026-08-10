"""Fail-closed runtime parsers for verified literature source snapshots."""

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
import hashlib
import math
import re
from tempfile import NamedTemporaryFile

from validation.literature_evidence_schema import ExtractionTrace
from validation.literature_evidence_sources import (
    SourceEvidenceError,
    VerifiedSource,
    _extract_text,
)


class SourceParserError(ValueError):
    """Raised when verified source text cannot establish a requested target."""


SUPPORTED_RECORD_OUTPUT_TYPES = frozenset(
    {"boolean", "number", "string", "list[number]", "list[string]"}
)
PARSER_KINDS_BY_RECORD_OUTPUT_TYPE = {
    "boolean": frozenset({"typed_claim"}),
    "number": frozenset({"numeric", "table_numeric"}),
    "string": frozenset({"scalar_string"}),
    "list[number]": frozenset({"interval", "sequence", "set"}),
    "list[string]": frozenset({"sequence", "set"}),
}
SUPPORTED_LOCATOR_KINDS = frozenset(
    {"abstract", "body_text", "equation", "figure_caption", "table", "field_map"}
)
PARSER_KINDS_BY_RECORD_LOCATOR_CLASS = {
    "abstract": frozenset(
        {"numeric", "interval", "sequence", "set", "typed_claim", "scalar_string"}
    ),
    "body_text": frozenset(
        {"numeric", "interval", "sequence", "set", "typed_claim", "scalar_string"}
    ),
    "equation": frozenset(
        {"numeric", "interval", "sequence", "set", "equation", "scalar_string"}
    ),
    "figure_caption": frozenset(
        {"numeric", "interval", "sequence", "set", "typed_claim", "scalar_string"}
    ),
}
SUPPORTED_PARSER_KINDS = frozenset(
    {
        "numeric",
        "interval",
        "sequence",
        "set",
        "equation",
        "table_numeric",
        "typed_claim",
        "scalar_string",
        "field_map",
    }
)


_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CATEGORICAL_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:\(\d+\))?" r"(?:[eE][+-]?\d+)?"
_NUMBER_TERMINATOR = r"(?=$|[\s,;:!?)}\]]|\.(?=$|\s))"
_FORBIDDEN_INPUT_KEYS = frozenset(
    {
        "expected",
        "expected_value",
        "target",
        "target_value",
        "registry_operand",
        "parsed_target",
        "strict_literature_match",
        "verdict",
    }
)


def _require_exact_keys(value, expected, label):
    if not isinstance(value, Mapping):
        raise SourceParserError(f"{label} must be a mapping")
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing:
        raise SourceParserError(f"{label} missing required field {missing[0]}")
    if extra:
        raise SourceParserError(f"{label} contains unsupported field {extra[0]}")


def _reject_forbidden_inputs(value, label):
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _FORBIDDEN_INPUT_KEYS:
                raise SourceParserError(f"forbidden {label} input key {key}")
            _reject_forbidden_inputs(item, label)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_forbidden_inputs(item, label)


def _require_nonempty_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise SourceParserError(f"{label} must be nonempty text")
    return value


def _require_identifier(value, label):
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise SourceParserError(f"{label} must be a lower-case identifier")
    return value


def _validate_verified_source(source):
    if not isinstance(source, VerifiedSource):
        raise SourceParserError("source must be a VerifiedSource")
    digest = hashlib.sha256(source.payload_bytes).hexdigest()
    if digest != source.payload_sha256:
        raise SourceParserError("verified source payload hash mismatch")
    if digest != source.provenance.raw_payload_sha256:
        raise SourceParserError("verified source provenance hash mismatch")
    if len(source.payload_bytes) != source.provenance.raw_payload_byte_length:
        raise SourceParserError("verified source payload length mismatch")
    if source.source_id != source.provenance.source_id:
        raise SourceParserError("verified source identity mismatch")
    citation_verification = source.provenance.citation_metadata_verification
    citation_verified = (
        citation_verification.get("verified") is True
        or citation_verification.get("status") == "verified"
    )
    if not citation_verified:
        raise SourceParserError("source citation metadata is not verified")
    if not isinstance(source.extracted_text, str) or not source.extracted_text.strip():
        raise SourceParserError("verified source has no extracted text")
    if not isinstance(source.extraction_tool, Mapping) or not source.extraction_tool:
        raise SourceParserError("verified source has no extraction-tool contract")
    if source.provenance.media_type == "application/pdf":
        try:
            path_payload = source.payload_path.read_bytes()
        except OSError as exc:
            raise SourceParserError(
                "verified PDF payload path cannot be re-read"
            ) from exc
        if path_payload != source.payload_bytes:
            raise SourceParserError("verified PDF path payload mismatch")
    descriptor_version = 1
    if source.provenance.media_type == "text/html":
        recorded_version = source.extraction_tool.get("version")
        if isinstance(recorded_version, int) and not isinstance(recorded_version, bool):
            descriptor_version = recorded_version
    try:
        if source.provenance.media_type == "application/pdf":
            with NamedTemporaryFile(suffix=".pdf") as payload_snapshot:
                payload_snapshot.write(source.payload_bytes)
                payload_snapshot.flush()
                deterministic_text = _extract_text(
                    Path(payload_snapshot.name),
                    source.payload_bytes,
                    source.provenance.media_type,
                    source.extraction_tool,
                    html_descriptor_version=descriptor_version,
                )
        else:
            deterministic_text = _extract_text(
                source.payload_path,
                source.payload_bytes,
                source.provenance.media_type,
                source.extraction_tool,
                html_descriptor_version=descriptor_version,
            )
    except (OSError, SourceEvidenceError) as exc:
        raise SourceParserError(
            "verified source deterministic payload extraction failed"
        ) from exc
    if deterministic_text != source.extracted_text:
        raise SourceParserError(
            "extracted text does not match deterministic payload extraction"
        )


def _validate_primary_claim_source(source, parser):
    if parser.get("kind") != "typed_claim":
        return
    if parser.get("claim_context") not in {
        "primary_experimental",
        "primary_model",
    }:
        return
    title = source.provenance.bibliographic_metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        raise SourceParserError("primary claim requires a bibliographic title")
    if re.search(r"\breviews?\b", title, flags=re.IGNORECASE):
        raise SourceParserError(
            "primary claim cannot use review bibliographic provenance"
        )
    role_verification = source.provenance.citation_metadata_verification.get(
        "source_role_verification"
    )
    if not isinstance(role_verification, Mapping):
        raise SourceParserError(
            "primary claim requires positive source-role verification"
        )
    _require_exact_keys(
        role_verification,
        {
            "status",
            "source_roles",
            "bibliographic_title_sha256",
            "raw_payload_sha256",
        },
        "source_role_verification",
    )
    source_roles = role_verification["source_roles"]
    if (
        isinstance(source_roles, (str, bytes, bytearray, Mapping))
        or not isinstance(source_roles, (list, tuple))
        or not source_roles
        or len(set(source_roles)) != len(source_roles)
        or any(
            role not in {"primary_experimental", "primary_model"}
            for role in source_roles
        )
    ):
        raise SourceParserError("source-role verification roles are invalid")
    if role_verification["status"] != "verified":
        raise SourceParserError("source-role verification status is not verified")
    if parser["claim_context"] not in source_roles:
        raise SourceParserError(
            "source-role verification does not cover the claim context"
        )
    if role_verification["bibliographic_title_sha256"] != _text_sha256(title):
        raise SourceParserError(
            "source-role verification bibliographic title hash mismatch"
        )
    if role_verification["raw_payload_sha256"] != source.payload_sha256:
        raise SourceParserError("source-role verification payload hash mismatch")
    return dict(role_verification)


def _nth_literal_span(text, literal, occurrence):
    if (
        isinstance(occurrence, bool)
        or not isinstance(occurrence, int)
        or occurrence < 1
    ):
        raise SourceParserError("locator occurrence must be a positive integer")
    start = -1
    search_from = 0
    for _ in range(occurrence):
        start = text.find(literal, search_from)
        if start < 0:
            raise SourceParserError(
                f"locator label {literal!r} occurrence {occurrence} was not found"
            )
        search_from = start + len(literal)
    return start, start + len(literal)


def _flexible_literal_pattern(literal):
    literal = _require_nonempty_text(literal, "source anchor")
    return r"\s+".join(
        re.escape(component) for component in re.split(r"\s+", literal.strip())
    )


def _single_flexible_span(text, start, end, literal, label):
    matches = list(re.finditer(_flexible_literal_pattern(literal), text[start:end]))
    if len(matches) != 1:
        raise SourceParserError(
            f"{label} must resolve to exactly one whitespace-flexible source span"
        )
    match = matches[0]
    return start + match.start(), start + match.end()


def _equation_line(text, locator):
    _require_exact_keys(locator, {"kind", "label", "occurrence"}, "locator")
    if locator["kind"] != "equation":
        raise SourceParserError("parser currently requires an equation locator")
    label = _require_nonempty_text(locator["label"], "locator label")
    label_start, _ = _nth_literal_span(text, label, locator["occurrence"])
    line_start = text.rfind("\n", 0, label_start) + 1
    line_end = text.find("\n", label_start)
    if line_end < 0:
        line_end = len(text)
    excerpt_start = label_start
    excerpt_end = line_end
    while excerpt_end > excerpt_start and text[excerpt_end - 1].isspace():
        excerpt_end -= 1
    return excerpt_start, excerpt_end, text[line_start:line_end]


def _body_text_line(text, locator):
    _require_exact_keys(locator, {"kind", "anchor", "occurrence"}, "locator")
    if locator["kind"] not in {"body_text", "abstract", "figure_caption"}:
        raise SourceParserError("text-container locator kind mismatch")
    anchor = _require_nonempty_text(locator["anchor"], "locator anchor")
    anchor_start, _ = _nth_literal_span(text, anchor, locator["occurrence"])
    line_start = text.rfind("\n", 0, anchor_start) + 1
    line_end = text.find("\n", anchor_start)
    if line_end < 0:
        line_end = len(text)
    excerpt_end = line_end
    while excerpt_end > line_start and text[excerpt_end - 1].isspace():
        excerpt_end -= 1
    return line_start, excerpt_end, text[line_start:line_end]


def _text_container_span(text, locator):
    _require_exact_keys(
        locator,
        {
            "kind",
            "start_anchor",
            "start_occurrence",
            "end_anchor",
            "end_occurrence",
        },
        "locator",
    )
    if locator["kind"] not in {"body_text", "abstract", "figure_caption"}:
        raise SourceParserError("text-container locator kind mismatch")
    start_anchor = _require_nonempty_text(
        locator["start_anchor"], "locator start_anchor"
    )
    end_anchor = _require_nonempty_text(locator["end_anchor"], "locator end_anchor")
    start, start_end = _nth_literal_span(
        text, start_anchor, locator["start_occurrence"]
    )
    relative_end_start, relative_end = _nth_literal_span(
        text[start_end:], end_anchor, locator["end_occurrence"]
    )
    end_start = start_end + relative_end_start
    end = start_end + relative_end
    if end_start < start_end or end <= start:
        raise SourceParserError("text-container end anchor precedes start anchor")
    return start, end, text[start:end]


def _located_line(text, locator):
    if not isinstance(locator, Mapping):
        raise SourceParserError("locator must be a mapping")
    locator_kind = locator.get("kind")
    if locator_kind == "equation":
        return _equation_line(text, locator)
    if locator_kind in {"body_text", "abstract", "figure_caption"}:
        if "start_anchor" in locator or "end_anchor" in locator:
            return _text_container_span(text, locator)
        return _body_text_line(text, locator)
    raise SourceParserError(f"unsupported locator kind {locator_kind!r}")


def _reject_ambiguous_target_label(excerpt, value_label, separator):
    label_pattern = re.escape(value_label) + r"\s*" + re.escape(separator)
    if sum(1 for _ in re.finditer(label_pattern, excerpt)) > 1:
        raise SourceParserError(f"ambiguous target label {value_label!r}")


def _parse_parenthetical_number(raw_value):
    match = re.fullmatch(
        r"(?P<mantissa>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
        r"(?:\((?P<uncertainty>\d+)\))?"
        r"(?P<exponent>[eE][+-]?\d+)?",
        raw_value,
    )
    if match is None:
        raise SourceParserError("numeric target is malformed")
    exponent_text = match.group("exponent") or ""
    value = float(match.group("mantissa") + exponent_text)
    if not math.isfinite(value):
        raise SourceParserError("numeric target must be finite")
    uncertainty_digits = match.group("uncertainty")
    uncertainty = None
    if uncertainty_digits is not None:
        mantissa = match.group("mantissa")
        exponent_match = re.search(r"[eE]([+-]?\d+)$", exponent_text)
        exponent = int(exponent_match.group(1)) if exponent_match else 0
        decimal_places = len(mantissa.partition(".")[2])
        uncertainty = float(
            Decimal(uncertainty_digits).scaleb(exponent - decimal_places)
        )
    return value, uncertainty


def _numeric_target(text, excerpt_start, excerpt_end, parser):
    _require_exact_keys(
        parser,
        {"kind", "field_id", "value_label", "units", "uncertainty"},
        "parser",
    )
    if parser["kind"] != "numeric":
        raise SourceParserError(f"unsupported parser kind {parser['kind']!r}")
    field_id = _require_identifier(parser["field_id"], "parser field_id")
    value_label = _require_nonempty_text(parser["value_label"], "parser value_label")
    units = _require_nonempty_text(parser["units"], "parser units")
    if parser["uncertainty"] != "parenthetical_last_digits":
        raise SourceParserError("unsupported numeric uncertainty convention")
    excerpt = text[excerpt_start:excerpt_end]
    _reject_ambiguous_target_label(excerpt, value_label, "=")
    match = re.search(
        re.escape(value_label)
        + r"\s*=\s*(?P<value>"
        + _NUMBER_PATTERN
        + r")"
        + _NUMBER_TERMINATOR,
        excerpt,
    )
    if match is None:
        raise SourceParserError(
            f"equation does not contain a numeric value for {value_label!r}"
        )
    raw_value = match.group("value")
    value, uncertainty = _parse_parenthetical_number(raw_value)
    value_start = excerpt_start + match.start("value")
    value_end = excerpt_start + match.end("value")
    return (
        raw_value,
        {field_id: value},
        {
            "kind": "numeric",
            "fields": [
                {
                    "id": field_id,
                    "type": "number",
                    "units": units,
                    "uncertainty": uncertainty,
                }
            ],
        },
        (value_start, value_end),
    )


def _phase_border_relation_token(token, *, side):
    directed_tokens = {
        "lower": {"<", "<=", "≤", "≲"},
        "upper": {">", ">=", "≥", "≳"},
    }
    if token in directed_tokens[side]:
        return token
    aps_pdftotext_tokens = {"lower": "\x02", "upper": "\x03"}
    if token == aps_pdftotext_tokens[side]:
        return token
    raise SourceParserError(f"unsupported {side} phase-border relation token {token!r}")


def _bordered_phase_interval_target(text, excerpt_start, excerpt_end, parser):
    _require_exact_keys(
        parser,
        {
            "kind",
            "field_id",
            "region_label",
            "variable",
            "lower_phase_anchor",
            "upper_phase_anchor",
            "normalization_anchor",
            "units",
            "output_type",
        },
        "parser",
    )
    if parser["kind"] != "interval":
        raise SourceParserError("phase-border parser kind mismatch")
    field_id = _require_identifier(parser["field_id"], "parser field_id")
    region_label = _require_nonempty_text(parser["region_label"], "parser region_label")
    variable = _require_nonempty_text(parser["variable"], "parser variable")
    lower_phase = _require_nonempty_text(
        parser["lower_phase_anchor"], "parser lower_phase_anchor"
    )
    upper_phase = _require_nonempty_text(
        parser["upper_phase_anchor"], "parser upper_phase_anchor"
    )
    _require_nonempty_text(
        parser["normalization_anchor"], "parser normalization_anchor"
    )
    units = _require_nonempty_text(parser["units"], "parser units")
    if parser["output_type"] != "list[number]":
        raise SourceParserError(
            "approximate phase-border interval must emit list[number] endpoints"
        )
    scalar_pattern = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"
    pattern = (
        _flexible_literal_pattern(region_label)
        + r"\s+"
        + _flexible_literal_pattern(lower_phase)
        + r"\s+for\s+"
        + _flexible_literal_pattern(variable)
        + r"\s+(?P<lower_relation>[^\w\s]+)\s*(?P<lower>"
        + scalar_pattern
        + r")\s+and\s+"
        + _flexible_literal_pattern(upper_phase)
        + r"\s+for\s+"
        + _flexible_literal_pattern(variable)
        + r"\s+(?P<upper_relation>[^\w\s]+)\s*(?P<upper>"
        + scalar_pattern
        + r")"
    )
    excerpt = text[excerpt_start:excerpt_end]
    matches = list(re.finditer(pattern, excerpt))
    if len(matches) != 1:
        raise SourceParserError(
            "source span must contain exactly one bordered phase-window clause"
        )
    match = matches[0]
    lower_relation = _phase_border_relation_token(
        match.group("lower_relation"), side="lower"
    )
    upper_relation = _phase_border_relation_token(
        match.group("upper_relation"), side="upper"
    )
    lower = float(match.group("lower"))
    upper = float(match.group("upper"))
    if not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper:
        raise SourceParserError(
            "phase-border endpoints must be finite and strictly ordered"
        )
    raw_start = match.start("lower")
    raw_end = match.end("upper")
    bounds = {
        "lower": lower,
        "upper": upper,
        "boundary_semantics": "source_approximate_phase_borders",
        "lower_relation_token": lower_relation,
        "upper_relation_token": upper_relation,
    }
    return (
        excerpt[raw_start:raw_end],
        {field_id: (lower, upper)},
        {
            "kind": "interval",
            "bounds": bounds,
            "fields": [
                {
                    "id": field_id,
                    "type": "list[number]",
                    "units": units,
                }
            ],
        },
        (excerpt_start + raw_start, excerpt_start + raw_end),
    )


def _interval_target(text, excerpt_start, excerpt_end, parser):
    if isinstance(parser, Mapping) and "region_label" in parser:
        return _bordered_phase_interval_target(text, excerpt_start, excerpt_end, parser)
    _require_exact_keys(
        parser,
        {
            "kind",
            "field_id",
            "value_label",
            "variable",
            "units",
            "output_type",
        },
        "parser",
    )
    field_id = _require_identifier(parser["field_id"], "parser field_id")
    value_label = _require_nonempty_text(parser["value_label"], "parser value_label")
    variable = _require_nonempty_text(parser["variable"], "parser variable")
    units = _require_nonempty_text(parser["units"], "parser units")
    output_type = parser["output_type"]
    if output_type not in {"interval[number]", "list[number]"}:
        raise SourceParserError("interval output_type is unsupported")
    excerpt = text[excerpt_start:excerpt_end]
    _reject_ambiguous_target_label(excerpt, value_label, ":")
    scalar_pattern = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"
    match = re.search(
        re.escape(value_label)
        + r"\s*:\s*(?P<lower>"
        + scalar_pattern
        + r")\s*(?P<lower_relation><=|<|≤)\s*"
        + re.escape(variable)
        + r"\s*(?P<upper_relation><=|<|≤)\s*(?P<upper>"
        + scalar_pattern
        + r")"
        + _NUMBER_TERMINATOR,
        excerpt,
    )
    if match is None:
        raise SourceParserError(
            f"equation does not contain a bounded interval for {variable!r}"
        )
    lower = float(match.group("lower"))
    upper = float(match.group("upper"))
    if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
        raise SourceParserError("interval bounds must be finite and ordered")
    lower_inclusive = match.group("lower_relation") in ("<=", "≤")
    upper_inclusive = match.group("upper_relation") in ("<=", "≤")
    if lower == upper and not (lower_inclusive and upper_inclusive):
        raise SourceParserError("interval must be nonempty")
    raw_start = match.start("lower")
    raw_end = match.end("upper")
    raw_value = excerpt[raw_start:raw_end]
    value_start = excerpt_start + raw_start
    value_end = excerpt_start + raw_end
    bounds = {
        "lower": lower,
        "upper": upper,
        "lower_inclusive": lower_inclusive,
        "upper_inclusive": upper_inclusive,
    }
    normalized = {
        field_id: bounds if output_type == "interval[number]" else (lower, upper)
    }
    typed_claim = {
        "kind": "interval",
        "bounds": bounds,
        "fields": [
            {
                "id": field_id,
                "type": output_type,
                "units": units,
            }
        ],
    }
    return raw_value, normalized, typed_claim, (value_start, value_end)


def _collection_target(text, excerpt_start, excerpt_end, parser):
    _require_exact_keys(
        parser,
        {
            "kind",
            "field_id",
            "value_label",
            "delimiter",
            "item_type",
            "output_type",
            "units",
        },
        "parser",
    )
    parser_kind = parser["kind"]
    if parser_kind not in {"sequence", "set"}:
        raise SourceParserError("collection parser kind mismatch")
    field_id = _require_identifier(parser["field_id"], "parser field_id")
    value_label = _require_nonempty_text(parser["value_label"], "parser value_label")
    units = _require_nonempty_text(parser["units"], "parser units")
    delimiter = parser["delimiter"]
    if delimiter not in {",", ";", "->"}:
        raise SourceParserError("collection delimiter is unsupported")
    item_type = parser["item_type"]
    if item_type not in {"string", "number"}:
        raise SourceParserError("collection item_type must be string or number")
    output_type = parser["output_type"]
    if output_type != f"list[{item_type}]":
        raise SourceParserError(
            "collection output_type must match its declared item_type"
        )
    excerpt = text[excerpt_start:excerpt_end]
    _reject_ambiguous_target_label(excerpt, value_label, "=")
    match = re.search(
        re.escape(value_label) + r"\s*=\s*(?P<value>[^\r\n]+?)\s*$",
        excerpt,
    )
    if match is None:
        raise SourceParserError(
            f"source line does not contain a collection for {value_label!r}"
        )
    raw_value = match.group("value").strip()
    raw_items = raw_value.split(delimiter)
    normalized_tokens = tuple(" ".join(item.split()) for item in raw_items)
    if not normalized_tokens or any(not item for item in normalized_tokens):
        raise SourceParserError("collection contains an empty item")
    if item_type == "string":
        if any(
            re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*(?: [A-Za-z0-9_-]+)*", item) is None
            for item in normalized_tokens
        ):
            raise SourceParserError("collection contains a malformed string item")
        items = normalized_tokens
    else:
        try:
            items = tuple(float(item) for item in normalized_tokens)
        except ValueError as exc:
            raise SourceParserError(
                "numeric collection contains a nonnumeric item"
            ) from exc
        if any(not math.isfinite(item) for item in items):
            raise SourceParserError("numeric collection items must be finite")
    if parser_kind == "set":
        if len(set(items)) != len(items):
            raise SourceParserError("set contains duplicate items")
        normalized_items = tuple(sorted(items))
    else:
        normalized_items = items
    raw_start = match.start("value")
    raw_end = match.end("value")
    while raw_end > raw_start and excerpt[raw_end - 1].isspace():
        raw_end -= 1
    return (
        raw_value,
        {field_id: normalized_items},
        {
            "kind": parser_kind,
            "fields": [
                {
                    "id": field_id,
                    "type": output_type,
                    "units": units,
                }
            ],
        },
        (excerpt_start + raw_start, excerpt_start + raw_end),
    )


def _validate_symbolic_expression(expression):
    if not expression:
        raise SourceParserError("equation expression is empty")
    allowed_punctuation = frozenset("._+-*/^()[]{} =|")
    if "__" in expression:
        raise SourceParserError("equation contains an unsupported token")
    if any(
        not (character.isalnum() or character in allowed_punctuation)
        for character in expression
    ):
        raise SourceParserError("equation contains an unsupported token")
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for character in expression:
        if character in "([{":
            stack.append(character)
        elif character in pairs:
            if not stack or stack.pop() != pairs[character]:
                raise SourceParserError("equation has unbalanced delimiters")
    if stack:
        raise SourceParserError("equation has unbalanced delimiters")


def _normalized_equation_component(component):
    operator_normalizations = str.maketrans(
        {
            "−": "-",
            "–": "-",
            "×": "*",
            "·": "*",
        }
    )
    return " ".join(component.translate(operator_normalizations).split())


def _equation_target(text, excerpt_start, excerpt_end, parser):
    _require_exact_keys(
        parser,
        {"kind", "field_id", "value_label", "units"},
        "parser",
    )
    field_id = _require_identifier(parser["field_id"], "parser field_id")
    value_label = _require_nonempty_text(parser["value_label"], "parser value_label")
    units = _require_nonempty_text(parser["units"], "parser units")
    excerpt = text[excerpt_start:excerpt_end]
    labelled_match = re.search(
        re.escape(value_label) + r"\s*:\s*(?P<value>[^\r\n]+?)\s*$",
        excerpt,
    )
    if labelled_match is not None:
        _reject_ambiguous_target_label(excerpt, value_label, ":")
        match = labelled_match
    else:
        _reject_ambiguous_target_label(excerpt, value_label, "=")
        match = re.search(
            r"(?P<value>"
            + re.escape(value_label)
            + r"\s*=\s*[^\r\n]+?)"
            + r"(?=(?:,\s*)?\(\d+[A-Za-z]?\)(?:\s|$)|$)",
            excerpt,
        )
    if match is None:
        raise SourceParserError(
            f"source line does not contain an equation for {value_label!r}"
        )
    raw_value = match.group("value").strip()
    relation_matches = list(re.finditer(r"(?<![<>])=(?!=)", raw_value))
    if len(relation_matches) != 1:
        raise SourceParserError("equation must contain exactly one equality relation")
    relation_match = relation_matches[0]
    lhs = _normalized_equation_component(raw_value[: relation_match.start()])
    rhs = _normalized_equation_component(raw_value[relation_match.end():])
    _validate_symbolic_expression(lhs)
    _validate_symbolic_expression(rhs)
    raw_start = match.start("value")
    raw_end = match.end("value")
    while raw_start < raw_end and excerpt[raw_start].isspace():
        raw_start += 1
    while raw_end > raw_start and excerpt[raw_end - 1].isspace():
        raw_end -= 1
    return (
        raw_value,
        {field_id: {"lhs": lhs, "relation": "=", "rhs": rhs}},
        {
            "kind": "equation",
            "fields": [
                {
                    "id": field_id,
                    "type": "equation",
                    "units": units,
                }
            ],
        },
        (excerpt_start + raw_start, excerpt_start + raw_end),
    )


def _split_table_line(line, delimiter):
    cells = []
    segment_start = 0
    for delimiter_match in re.finditer(re.escape(delimiter), line):
        segment_end = delimiter_match.start()
        cells.append((segment_start, segment_end, line[segment_start:segment_end]))
        segment_start = delimiter_match.end()
    cells.append((segment_start, len(line), line[segment_start:]))
    normalized = []
    for start, end, raw in cells:
        left_trim = len(raw) - len(raw.lstrip())
        right_trimmed = raw.rstrip()
        normalized.append((start + left_trim, start + len(right_trimmed), raw.strip()))
    return tuple(normalized)


def _fixed_width_header_cells(header):
    cells = []
    segment_start = 0
    for separator in re.finditer(r"\s{2,}", header):
        raw = header[segment_start:separator.start()]
        if raw:
            left_trim = len(raw) - len(raw.lstrip())
            right_trimmed = raw.rstrip()
            cells.append(
                (
                    segment_start + left_trim,
                    segment_start + len(right_trimmed),
                    raw.strip(),
                )
            )
        segment_start = separator.end()
    raw = header[segment_start:]
    if raw:
        left_trim = len(raw) - len(raw.lstrip())
        right_trimmed = raw.rstrip()
        cells.append(
            (
                segment_start + left_trim,
                segment_start + len(right_trimmed),
                raw.strip(),
            )
        )
    names = tuple(cell[2] for cell in cells)
    if len(cells) < 2 or any(not name for name in names):
        raise SourceParserError(
            "fixed-width table header requires at least two nonempty cells"
        )
    if len(set(names)) != len(names):
        raise SourceParserError("fixed-width table header cells must be unique")
    return tuple(cells)


def _fixed_width_column_windows(cells, header_length):
    windows = []
    for index, cell in enumerate(cells):
        left = 0 if index == 0 else (cells[index - 1][1] + cell[0]) // 2
        right = (
            header_length
            if index == len(cells) - 1
            else (cell[1] + cells[index + 1][0] + 1) // 2
        )
        if left >= right:
            raise SourceParserError("fixed-width table column windows overlap")
        windows.append((left, right))
    return tuple(windows)


def _parse_aps_pdftotext_parenthetical(raw_value):
    match = re.fullmatch(
        r"(?P<mantissa>[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
        r"~(?P<uncertainty>\d+)!"
        r"(?P<exponent>[eE][+-]?\d+)?",
        raw_value,
    )
    if match is None:
        raise SourceParserError(
            "APS pdftotext table value lacks encoded parenthetical uncertainty"
        )
    conventional = (
        match.group("mantissa")
        + "("
        + match.group("uncertainty")
        + ")"
        + (match.group("exponent") or "")
    )
    return _parse_parenthetical_number(conventional)


def _fixed_width_table_numeric_target(text, locator, parser):
    _require_exact_keys(
        locator,
        {
            "kind",
            "label",
            "occurrence",
            "layout",
            "header",
            "row_label",
            "value_column",
            "unit_anchor",
            "unit_anchor_occurrence",
        },
        "locator",
    )
    if locator["kind"] != "table" or locator["layout"] != "fixed_width":
        raise SourceParserError("fixed-width table locator kind mismatch")
    _require_exact_keys(
        parser,
        {
            "kind",
            "field_id",
            "units",
            "uncertainty",
            "value_convention",
        },
        "parser",
    )
    if parser["kind"] != "table_numeric":
        raise SourceParserError("fixed-width table parser kind mismatch")
    if parser["uncertainty"] != "aps_pdftotext_parenthetical":
        raise SourceParserError(
            "fixed-width table uncertainty convention is unsupported"
        )
    if parser["value_convention"] != ("aps_pdftotext_minus_observable_magnitude"):
        raise SourceParserError("fixed-width table value convention is unsupported")
    field_id = _require_identifier(parser["field_id"], "parser field_id")
    units = _require_nonempty_text(parser["units"], "parser units")
    label = _require_nonempty_text(locator["label"], "locator label")
    header = _require_nonempty_text(locator["header"], "locator header")
    row_label = _require_nonempty_text(locator["row_label"], "locator row_label")
    value_column = _require_nonempty_text(
        locator["value_column"], "locator value_column"
    )
    _require_nonempty_text(locator["unit_anchor"], "locator unit_anchor")
    label_start, _ = _nth_literal_span(text, label, locator["occurrence"])
    page_end = text.find("\f", label_start)
    if page_end < 0:
        page_end = len(text)
    header_start, header_end = _single_literal_span(
        text,
        label_start,
        page_end,
        header,
        "fixed-width table header",
    )
    header_line_start = text.rfind("\n", 0, header_start) + 1
    header_line_end = text.find("\n", header_end)
    if header_line_end < 0:
        header_line_end = len(text)
    header_column = header_start - header_line_start
    header_cells = _fixed_width_header_cells(header)
    header_names = tuple(cell[2] for cell in header_cells)
    if value_column not in header_names:
        raise SourceParserError("fixed-width table is missing its value column")
    if value_column != "2E":
        raise SourceParserError(
            "APS minus-observable convention requires extracted 2E header"
        )
    value_index = header_names.index(value_column)
    windows = _fixed_width_column_windows(header_cells, len(header))

    matching_rows = []
    row_number = 0
    position = header_line_end + (1 if header_line_end < len(text) else 0)
    while position < page_end:
        row_end = text.find("\n", position)
        if row_end < 0:
            row_end = len(text)
        row_line = text[position:row_end]
        if not row_line.strip():
            break
        row_cells = []
        for left, right in windows:
            raw_cell = row_line[header_column + left:header_column + right]
            leading = len(raw_cell) - len(raw_cell.lstrip())
            trailing_end = len(raw_cell.rstrip())
            row_cells.append(
                (
                    header_column + left + leading,
                    header_column + left + trailing_end,
                    raw_cell.strip(),
                )
            )
        if any(not cell[2] for cell in row_cells):
            break
        row_number += 1
        if row_cells[0][2] == row_label:
            matching_rows.append((row_number, position, row_end, row_cells))
        position = row_end + (1 if row_end < len(text) else 0)
    if len(matching_rows) != 1:
        raise SourceParserError(
            f"fixed-width table must contain exactly one row labelled {row_label!r}"
        )
    row_number, row_start, row_end, row_cells = matching_rows[0]
    value_cell = row_cells[value_index]
    value, uncertainty = _parse_aps_pdftotext_parenthetical(value_cell[2])
    return (
        row_start,
        row_end,
        value_cell[2],
        {field_id: value},
        {
            "kind": "numeric",
            "fields": [
                {
                    "id": field_id,
                    "type": "number",
                    "units": units,
                    "uncertainty": uncertainty,
                    "convention": "source_column_minus_energy_magnitude",
                }
            ],
        },
        (row_start + value_cell[0], row_start + value_cell[1]),
        {
            "table_coordinates": {
                "table_label": label,
                "row_label": row_label,
                "row_number": row_number,
                "value_column": value_column,
                "value_column_number": value_index + 1,
                "layout": "fixed_width",
                "value_convention": "source_column_minus_energy_magnitude",
            }
        },
    )


def _table_numeric_target(text, locator, parser):
    if isinstance(locator, Mapping) and locator.get("layout") == "fixed_width":
        return _fixed_width_table_numeric_target(text, locator, parser)
    _require_exact_keys(
        locator,
        {
            "kind",
            "label",
            "occurrence",
            "delimiter",
            "row_label",
            "value_column",
            "uncertainty_column",
        },
        "locator",
    )
    if locator["kind"] != "table":
        raise SourceParserError("table-numeric parser requires a table locator")
    _require_exact_keys(
        parser,
        {"kind", "field_id", "units"},
        "parser",
    )
    field_id = _require_identifier(parser["field_id"], "parser field_id")
    units = _require_nonempty_text(parser["units"], "parser units")
    label = _require_nonempty_text(locator["label"], "locator label")
    row_label = _require_nonempty_text(locator["row_label"], "locator row_label")
    value_column = _require_nonempty_text(
        locator["value_column"], "locator value_column"
    )
    uncertainty_column = _require_nonempty_text(
        locator["uncertainty_column"], "locator uncertainty_column"
    )
    delimiter = locator["delimiter"]
    if delimiter not in {"|", ",", "\t"}:
        raise SourceParserError("table delimiter is unsupported")
    label_start, _ = _nth_literal_span(text, label, locator["occurrence"])
    label_line_end = text.find("\n", label_start)
    if label_line_end < 0:
        raise SourceParserError("table label has no following header row")
    position = label_line_end + 1
    header_end = text.find("\n", position)
    if header_end < 0:
        header_end = len(text)
    header_line = text[position:header_end]
    header_cells = _split_table_line(header_line, delimiter)
    header_names = tuple(cell[2] for cell in header_cells)
    if len(set(header_names)) != len(header_names) or any(
        not name for name in header_names
    ):
        raise SourceParserError("table header cells must be unique and nonempty")
    if value_column not in header_names or uncertainty_column not in header_names:
        raise SourceParserError(
            "table is missing a declared value or uncertainty column"
        )
    value_index = header_names.index(value_column)
    uncertainty_index = header_names.index(uncertainty_column)
    if value_index == uncertainty_index:
        raise SourceParserError("value and uncertainty columns must be distinct")

    matching_rows = []
    row_number = 0
    position = header_end + (1 if header_end < len(text) else 0)
    while position < len(text):
        row_end = text.find("\n", position)
        if row_end < 0:
            row_end = len(text)
        row_line = text[position:row_end]
        if not row_line.strip() or delimiter not in row_line:
            break
        row_number += 1
        cells = _split_table_line(row_line, delimiter)
        if len(cells) != len(header_cells):
            raise SourceParserError("table row column count does not match the header")
        if cells[0][2] == row_label:
            matching_rows.append((row_number, position, row_end, row_line, cells))
        position = row_end + (1 if row_end < len(text) else 0)
    if len(matching_rows) != 1:
        raise SourceParserError(
            f"table must contain exactly one row labelled {row_label!r}"
        )
    row_number, row_start, row_end, row_line, cells = matching_rows[0]
    value_cell = cells[value_index]
    uncertainty_cell = cells[uncertainty_index]
    try:
        value = float(value_cell[2])
        uncertainty = float(uncertainty_cell[2])
    except ValueError as exc:
        raise SourceParserError("table value and uncertainty must be numeric") from exc
    if not math.isfinite(value) or not math.isfinite(uncertainty) or uncertainty < 0:
        raise SourceParserError(
            "table value must be finite and uncertainty finite nonnegative"
        )
    return (
        row_start,
        row_end,
        value_cell[2],
        {field_id: value},
        {
            "kind": "numeric",
            "fields": [
                {
                    "id": field_id,
                    "type": "number",
                    "units": units,
                    "uncertainty": uncertainty,
                }
            ],
        },
        (row_start + value_cell[0], row_start + value_cell[1]),
        {
            "table_coordinates": {
                "table_label": label,
                "row_label": row_label,
                "row_number": row_number,
                "value_column": value_column,
                "value_column_number": value_index + 1,
                "uncertainty_column": uncertainty_column,
                "uncertainty_column_number": uncertainty_index + 1,
            }
        },
    )


def _primary_model_claim(excerpt, *, field_id, units, value_span):
    pattern = (
        r"(?P<method>Exact diagonalization|DMRG|Quantum Monte Carlo|"
        r"Analytic solution)\s+"
        r"(?P<qualifier>establishes|finds|rules out|suggests)\s+"
        r"(?P<subject>[A-Za-zΑ-Ωα-ω0-9]"
        r"[A-Za-zΑ-Ωα-ω0-9+_.()\[\]-]*)\s+"
        r"(?P<scope>model)\s+"
        r"(?P<observable>[A-Za-z][A-Za-z0-9+_. -]*?)\s+"
        r"at\s+zero\s+field\.?"
    )
    match = re.fullmatch(pattern, excerpt, flags=re.IGNORECASE)
    if match is None:
        raise SourceParserError(
            "primary model claim must directly bind method, model subject, "
            "observable, polarity, and conditions in one clause"
        )
    qualifier = " ".join(match.group("qualifier").casefold().split())
    if qualifier == "suggests":
        raise SourceParserError(
            "suggested model language is not a direct primary theoretical claim"
        )
    polarity = "negated" if qualifier == "rules out" else "affirmed"
    method_key = " ".join(match.group("method").casefold().split())
    method_ids = {
        "exact diagonalization": "exact_diagonalization",
        "dmrg": "dmrg",
        "quantum monte carlo": "quantum_monte_carlo",
        "analytic solution": "analytic_solution",
    }
    _validate_symbolic_expression(match.group("subject"))
    return (
        excerpt,
        {field_id: polarity == "affirmed"},
        {
            "kind": "categorical",
            "subject": match.group("subject"),
            "observable": " ".join(match.group("observable").split()),
            "scope": "model",
            "polarity": polarity,
            "qualifier": qualifier.replace(" ", "_"),
            "method": method_ids[method_key],
            "source_role": "primary_theoretical",
            "conditions": {"field": {"value": 0.0, "units": "T"}},
            "fields": [
                {
                    "id": field_id,
                    "type": "boolean",
                    "units": units,
                }
            ],
        },
        value_span,
    )


def _reported_material_finding(text, excerpt_start, excerpt_end, parser):
    _require_exact_keys(
        parser,
        {
            "kind",
            "field_id",
            "claim_context",
            "claim_syntax",
            "subject_anchor",
            "method_anchor",
            "observable_anchor",
            "finding_anchor",
            "condition_anchor",
            "units",
        },
        "parser",
    )
    if (
        parser["kind"] != "typed_claim"
        or parser["claim_context"] != "primary_experimental"
        or parser["claim_syntax"] != "reported_material_finding"
    ):
        raise SourceParserError("reported-material claim parser contract mismatch")
    field_id = _require_identifier(parser["field_id"], "parser field_id")
    units = _require_nonempty_text(parser["units"], "parser units")
    component_spans = {}
    for component in (
        "subject",
        "method",
        "observable",
        "finding",
        "condition",
    ):
        component_spans[component] = _single_flexible_span(
            text,
            excerpt_start,
            excerpt_end,
            parser[f"{component}_anchor"],
            f"reported-material {component}",
        )
    finding_start = component_spans["finding"][0]
    if any(
        component_spans[component][0] >= finding_start
        for component in ("subject", "method", "observable")
    ):
        raise SourceParserError(
            "reported-material subject, method, and observable must precede finding"
        )

    subject_start, subject_end = component_spans["subject"]
    subject_context = " ".join(
        text[max(excerpt_start, subject_start - 120):subject_start].casefold().split()
    )
    scope_markers = list(
        re.finditer(
            r"\b(?P<scope>compound|material|crystal|model|system)\b",
            subject_context,
        )
    )
    if not scope_markers or scope_markers[-1].group("scope") not in {
        "compound",
        "material",
        "crystal",
    }:
        raise SourceParserError(
            "reported-material subject lacks a direct material-scope marker"
        )
    subject = " ".join(text[subject_start:subject_end].split())
    _validate_symbolic_expression(subject)

    method_start, method_end = component_spans["method"]
    method_text = " ".join(text[method_start:method_end].split())
    method_ids = {
        "specific heat and inelastic neutron scattering": (
            "specific_heat_and_inelastic_neutron_scattering"
        ),
        "neutron powder diffraction and magnetic resonant x-ray diffraction": (
            "neutron_powder_and_magnetic_resonant_xray_diffraction"
        ),
    }
    method = method_ids.get(method_text.casefold())
    if method is None:
        raise SourceParserError(
            "reported-material method is not an allowed direct measurement"
        )

    observable_start, observable_end = component_spans["observable"]
    observable = " ".join(text[observable_start:observable_end].split())
    finding_end = component_spans["finding"][1]
    finding = " ".join(text[finding_start:finding_end].split())
    finding_folded = finding.casefold()
    qualifiers = (
        ("we did not observe", "did_not_observe", "negated"),
        ("we establish that", "establishes", "affirmed"),
        ("we observed", "observed", "affirmed"),
        ("we observe", "observes", "affirmed"),
        ("we find", "finds", "affirmed"),
    )
    qualifier = None
    polarity = None
    for prefix, candidate_qualifier, candidate_polarity in qualifiers:
        if finding_folded.startswith(prefix):
            qualifier = candidate_qualifier
            polarity = candidate_polarity
            break
    if finding_folded.startswith("we suggest"):
        raise SourceParserError(
            "suggested material language is not a direct experimental finding"
        )
    if qualifier is None:
        raise SourceParserError(
            "reported-material finding lacks a direct finding qualifier"
        )
    observable_core = re.sub(r"^\d+\s*[=/]\s*\d+\s+", "", observable.casefold())
    observable_core = re.sub(r"\s+phase$", "", observable_core)
    if not observable_core or observable_core not in finding_folded:
        raise SourceParserError(
            "reported-material finding does not restate the located observable"
        )

    condition_start, condition_end = component_spans["condition"]
    condition_statement = " ".join(text[condition_start:condition_end].split())
    typed_claim = {
        "kind": "categorical",
        "subject": subject,
        "observable": observable,
        "scope": "material",
        "polarity": polarity,
        "qualifier": qualifier,
        "method": method,
        "source_role": "primary_experimental",
        "conditions": {"source_statement": condition_statement},
        "fields": [
            {
                "id": field_id,
                "type": "boolean",
                "units": units,
            }
        ],
    }
    return (
        text[excerpt_start:excerpt_end],
        {field_id: polarity == "affirmed"},
        typed_claim,
        (excerpt_start, excerpt_end),
    )


def _typed_claim_target(text, excerpt_start, excerpt_end, parser):
    if (
        isinstance(parser, Mapping)
        and parser.get("claim_syntax") == "reported_material_finding"
    ):
        return _reported_material_finding(text, excerpt_start, excerpt_end, parser)
    _require_exact_keys(
        parser,
        {"kind", "field_id", "claim_context", "units"},
        "parser",
    )
    field_id = _require_identifier(parser["field_id"], "parser field_id")
    units = _require_nonempty_text(parser["units"], "parser units")
    claim_context = parser["claim_context"]
    source_excerpt = text[excerpt_start:excerpt_end]
    leading_space = len(source_excerpt) - len(source_excerpt.lstrip())
    trailing_space = len(source_excerpt) - len(source_excerpt.rstrip())
    value_start = excerpt_start + leading_space
    value_end = excerpt_end - trailing_space
    excerpt = text[value_start:value_end]
    if claim_context == "primary_model":
        return _primary_model_claim(
            excerpt,
            field_id=field_id,
            units=units,
            value_span=(value_start, value_end),
        )
    if claim_context != "primary_experimental":
        raise SourceParserError("unsupported typed-claim context")
    pattern = (
        r"(?P<method>Neutron diffraction|"
        r"Magnetic resonant x-ray diffraction|"
        r"X-ray diffraction|Muon spin rotation)\s+"
        r"(?P<qualifier>directly observed|observed|did not observe|suggested)\s+"
        r"(?P<subject>[A-Za-zΑ-Ωα-ω0-9]"
        r"[A-Za-zΑ-Ωα-ω0-9+_.()\[\]-]*)\s+"
        r"(?P<scope>material|compound|model|system)\s+"
        r"(?P<observable>[A-Za-z][A-Za-z0-9+_. -]*?)\s+"
        r"(?P<temperature_relation>below|above|at)\s+"
        r"(?P<temperature>"
        + _NUMBER_PATTERN
        + r")\s*K\s+at\s+(?:(?P<zero_field>zero)|(?P<field_value>"
        + _NUMBER_PATTERN
        + r")\s*(?P<field_units>T))\s+field\.?"
    )
    match = re.fullmatch(pattern, excerpt, flags=re.IGNORECASE)
    if match is None:
        raise SourceParserError(
            "primary experimental claim must directly bind method, subject, "
            "scope, observable, polarity, temperature, and field in one clause"
        )
    _validate_symbolic_expression(match.group("subject"))
    qualifier_text = " ".join(match.group("qualifier").casefold().split())
    if qualifier_text == "suggested":
        raise SourceParserError(
            "suggested model or material language is not primary experimental evidence"
        )
    scope = match.group("scope").casefold()
    if scope not in {"material", "compound"}:
        raise SourceParserError(
            "primary experimental material claim cannot be inferred from a model or system"
        )
    qualifier = (
        "directly_observed" if qualifier_text == "directly observed" else "observed"
    )
    polarity = "negated" if qualifier_text == "did not observe" else "affirmed"
    temperature, temperature_uncertainty = _parse_parenthetical_number(
        match.group("temperature")
    )
    if match.group("zero_field") is not None:
        field_value = 0.0
        field_uncertainty = None
    else:
        field_value, field_uncertainty = _parse_parenthetical_number(
            match.group("field_value")
        )
    method_key = " ".join(match.group("method").casefold().split())
    method_ids = {
        "neutron diffraction": "neutron_diffraction",
        "magnetic resonant x-ray diffraction": ("magnetic_resonant_xray_diffraction"),
        "x-ray diffraction": "xray_diffraction",
        "muon spin rotation": "muon_spin_rotation",
    }
    field_condition = {"value": field_value, "units": "T"}
    if field_uncertainty is not None:
        field_condition["uncertainty"] = field_uncertainty
    typed_claim = {
        "kind": "categorical",
        "subject": match.group("subject"),
        "observable": " ".join(match.group("observable").split()),
        "scope": "material" if scope == "compound" else scope,
        "polarity": polarity,
        "qualifier": qualifier,
        "method": method_ids[method_key],
        "source_role": "primary_experimental",
        "conditions": {
            "temperature": {
                "relation": match.group("temperature_relation").casefold(),
                "value": temperature,
                "units": "K",
                "uncertainty": temperature_uncertainty,
            },
            "field": field_condition,
        },
        "fields": [
            {
                "id": field_id,
                "type": "boolean",
                "units": units,
            }
        ],
    }
    return (
        excerpt,
        {field_id: polarity == "affirmed"},
        typed_claim,
        (value_start, value_end),
    )


def _scalar_string_target(text, excerpt_start, excerpt_end, parser):
    _require_exact_keys(
        parser,
        {"kind", "field_id", "value_label", "value_type", "units"},
        "parser",
    )
    field_id = _require_identifier(parser["field_id"], "parser field_id")
    value_label = _require_nonempty_text(parser["value_label"], "parser value_label")
    units = _require_nonempty_text(parser["units"], "parser units")
    value_type = parser["value_type"]
    if value_type not in {"categorical_label", "symbolic_expression"}:
        raise SourceParserError("scalar string value_type is unsupported")
    excerpt = text[excerpt_start:excerpt_end]
    _reject_ambiguous_target_label(excerpt, value_label, "=")
    match = re.search(
        re.escape(value_label) + r"\s*=\s*(?P<value>[^\r\n]+?)\s*$",
        excerpt,
    )
    if match is None:
        raise SourceParserError(
            f"source line does not contain a scalar string for {value_label!r}"
        )
    raw_value = match.group("value").strip()
    normalized_value = " ".join(raw_value.split())
    if value_type == "categorical_label":
        if _CATEGORICAL_LABEL_RE.fullmatch(normalized_value) is None:
            raise SourceParserError(
                "categorical source value must be one closed label token"
            )
    else:
        _validate_symbolic_expression(normalized_value)
    raw_start = match.start("value")
    raw_end = match.end("value")
    while raw_end > raw_start and excerpt[raw_end - 1].isspace():
        raw_end -= 1
    return (
        raw_value,
        {field_id: normalized_value},
        {
            "kind": "string",
            "fields": [
                {
                    "id": field_id,
                    "type": "string",
                    "units": units,
                    "convention": value_type,
                }
            ],
        },
        (excerpt_start + raw_start, excerpt_start + raw_end),
    )


def _coordinates(text, start, end):
    prefix = text[:start]
    excerpt = text[start:end]
    line_start = prefix.count("\n") + 1
    line_end = line_start + excerpt.count("\n")
    last_newline = prefix.rfind("\n")
    column_start = start - last_newline
    return {
        "coordinate_space": "verified_extracted_text_utf8",
        "character_start": start,
        "character_end": end,
        "byte_start": len(prefix.encode("utf-8")),
        "byte_end": len(text[:end].encode("utf-8")),
        "page_number": prefix.count("\f") + 1,
        "line_start": line_start,
        "line_end": line_end,
        "column_start": column_start,
    }


def _parser_code_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _text_sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _single_literal_span(text, start, end, literal, label):
    positions = []
    position = text.find(literal, start, end)
    while position >= 0:
        positions.append(position)
        position = text.find(literal, position + len(literal), end)
    if len(positions) != 1:
        raise SourceParserError(f"{label} must resolve to exactly one source span")
    return positions[0], positions[0] + len(literal)


def _literal_unit_after_value(text, value_end, excerpt_end):
    tail = text[value_end:excerpt_end]
    match = re.match(
        r"\s*(?P<unit>meV|eV|mK|K|T|radian|rad|rlu|%)" r"(?=$|[\s,.;:)\]])",
        tail,
    )
    if match is None:
        return None
    return (
        value_end + match.start("unit"),
        value_end + match.end("unit"),
    )


def _literal_unit_in_span(text, start, end):
    matches = list(
        re.finditer(
            r"(?<![A-Za-z0-9])(?P<unit>meV|eV|mK|radian|rad|rlu|%)" r"(?![A-Za-z0-9])",
            text[start:end],
        )
    )
    if not matches:
        return None
    if len(matches) != 1:
        raise SourceParserError("source contains ambiguous explicit unit tokens")
    match = matches[0]
    return start + match.start("unit"), start + match.end("unit")


def _table_header_unit_span(text, locator, excerpt_start):
    label_start, _ = _nth_literal_span(text, locator["label"], locator["occurrence"])
    column_start, column_end = _single_literal_span(
        text,
        label_start,
        excerpt_start,
        locator["value_column"],
        "table value-column unit evidence",
    )
    return _literal_unit_in_span(text, column_start, column_end)


def _semantic_unit_rule(units, field_type, raw_evidence, parser_kind):
    compact = "".join(raw_evidence.casefold().split())
    if units == "not_applicable":
        if not (field_type in {"boolean", "string"} or field_type.endswith("[string]")):
            raise SourceParserError(
                "not_applicable units require a categorical or string field"
            )
        return "nonphysical_claim_semantics"
    if units == "dimensionless_j2_over_j1" and (
        "j2/j1" in compact or "j1=1" in compact
    ):
        return "j2_over_j1_ratio"
    if units == "dimensionless_ratio" and ("/" in compact or "ratio" in compact):
        return "dimensionless_ratio_expression"
    if units == "reciprocal_lattice_unit" and any(
        marker in compact for marker in ("reciprocallatticeunit", "rlu")
    ):
        return "reciprocal_vector_label"
    if (
        units == "dimensionless_equation"
        and parser_kind == "equation"
        and "dimensionless" in compact
    ):
        return "dimensionless_equation_expression"
    exchange_scale_is_explicit = (
        re.search(r"(?:^|[^A-Za-z])J(?:$|[^A-Za-z])", raw_evidence) is not None
        or "unitsofj" in compact
        or "j=1" in compact
        or "hamiltonianwrittenas(j51)" in compact
    )
    if (
        units == "exchange_energy_per_site"
        and any(
            marker in compact
            for marker in ("energy_per_site", "energypersite", "persite")
        )
        and exchange_scale_is_explicit
    ):
        return "exchange_energy_per_site_label"
    if (
        units == "exchange_energy_per_spin"
        and any(
            marker in compact
            for marker in ("energy_per_spin", "energyperspin", "perspin")
        )
        and exchange_scale_is_explicit
    ):
        return "exchange_energy_per_spin_label"
    if units == "exchange_energy_unit" and (
        re.search(
            r"(?:^|[^A-Za-z])J(?=$|[^A-Za-z]|S[A-Za-z0-9])",
            raw_evidence,
        )
        is not None
    ):
        return "exchange_scale_in_expression"
    if units == "count" and any(
        marker in compact for marker in ("count", "number", "degenerac")
    ):
        return "count_label"
    raise SourceParserError(
        f"source text does not prove declared normalized units {units!r}"
    )


def _unit_statement_spans(text, contract):
    _require_exact_keys(contract, {"kind", "anchors"}, "unit_evidence")
    if contract["kind"] != "source_statements":
        raise SourceParserError("unit_evidence kind is unsupported")
    anchors = contract["anchors"]
    if (
        isinstance(anchors, (str, bytes, bytearray, Mapping))
        or not isinstance(anchors, (list, tuple))
        or not anchors
        or len(anchors) > 8
    ):
        raise SourceParserError(
            "unit_evidence anchors must be a bounded nonempty sequence"
        )
    spans = []
    identities = set()
    for index, anchor in enumerate(anchors):
        _require_exact_keys(
            anchor,
            {"text", "occurrence"},
            f"unit_evidence anchors[{index}]",
        )
        anchor_text = _require_nonempty_text(
            anchor["text"], f"unit_evidence anchors[{index}] text"
        )
        identity = (anchor_text, anchor["occurrence"])
        if identity in identities:
            raise SourceParserError("unit_evidence contains a duplicate anchor")
        identities.add(identity)
        spans.append(_nth_literal_span(text, anchor_text, anchor["occurrence"]))
    return tuple(spans)


def _render_unit_evidence(text, spans, units, normalization_rule):
    fragments = tuple(
        {
            "raw_text": text[start:end],
            "coordinates": _coordinates(text, start, end),
            "sha256": _text_sha256(text[start:end]),
        }
        for start, end in spans
    )
    if len(fragments) == 1:
        raw_units = fragments[0]["raw_text"]
        coordinates = fragments[0]["coordinates"]
        digest = fragments[0]["sha256"]
    else:
        raw_units = tuple(fragment["raw_text"] for fragment in fragments)
        coordinates = tuple(fragment["coordinates"] for fragment in fragments)
        digest = tuple(fragment["sha256"] for fragment in fragments)
    return {
        "raw_units": raw_units,
        "normalized_units": units,
        "normalization_rule": normalization_rule,
        "coordinates": coordinates,
        "sha256": digest,
        "source_fragments": fragments,
    }


def _unit_evidence(
    *,
    text,
    excerpt_start,
    excerpt_end,
    value_span,
    parser_kind,
    parser,
    locator,
    typed_claim,
    unit_contract,
):
    fields = typed_claim.get("fields")
    if not isinstance(fields, (list, tuple)) or len(fields) != 1:
        raise SourceParserError("leaf parser must emit exactly one typed field")
    field = fields[0]
    units = field["units"]
    field_type = field["type"]

    literal_span = None
    if parser_kind in {"numeric", "interval"}:
        literal_span = _literal_unit_after_value(text, value_span[1], excerpt_end)
    elif parser_kind == "table_numeric" and locator.get("layout") != "fixed_width":
        literal_span = _table_header_unit_span(text, locator, excerpt_start)
    elif parser_kind != "typed_claim":
        literal_span = _literal_unit_in_span(text, value_span[0], value_span[1])
    if literal_span is not None:
        unit_start, unit_end = literal_span
        raw_units = text[unit_start:unit_end]
        literal_normalizations = {
            "eV": "eV",
            "meV": "meV",
            "mK": "mK",
            "K": "K",
            "T": "T",
            "radian": "radian",
            "rad": "radian",
            "rlu": "reciprocal_lattice_unit",
            "%": "percent",
        }
        normalized_units = literal_normalizations[raw_units]
        if normalized_units != units:
            raise SourceParserError(
                f"source units {raw_units!r} disagree with declared "
                f"normalization {units!r}"
            )
        normalization_rule = "literal_unit_identity"
        spans = ((unit_start, unit_end),)
    elif unit_contract is not None:
        spans = _unit_statement_spans(text, unit_contract)
        raw_evidence = "\n".join(text[start:end] for start, end in spans)
        normalization_rule = _semantic_unit_rule(
            units, field_type, raw_evidence, parser_kind
        )
        normalized_units = units
    else:
        global_occurrence = None
        if parser_kind == "interval" and "normalization_anchor" in parser:
            basis = parser["normalization_anchor"]
            global_occurrence = 1
        elif parser_kind == "interval":
            basis = parser["variable"]
            basis_start, basis_end = value_span
        elif parser_kind == "table_numeric" and locator.get("layout") == "fixed_width":
            basis = locator["unit_anchor"]
            global_occurrence = locator["unit_anchor_occurrence"]
        elif parser_kind == "table_numeric":
            basis = locator["row_label"]
            basis_start, basis_end = excerpt_start, excerpt_end
        elif parser_kind in {"equation", "typed_claim"} or (
            parser_kind == "scalar_string" and units == "exchange_energy_unit"
        ):
            basis = text[value_span[0]:value_span[1]]
            basis_start, basis_end = value_span
        else:
            basis = parser["value_label"]
            basis_start, basis_end = excerpt_start, excerpt_end
        if global_occurrence is None:
            unit_start, unit_end = _single_literal_span(
                text,
                basis_start,
                basis_end,
                basis,
                "source unit evidence",
            )
        else:
            unit_start, unit_end = _nth_literal_span(text, basis, global_occurrence)
        raw_units = text[unit_start:unit_end]
        normalization_rule = _semantic_unit_rule(
            units, field_type, raw_units, parser_kind
        )
        normalized_units = units
        spans = ((unit_start, unit_end),)
    return _render_unit_evidence(text, spans, normalized_units, normalization_rule)


def _parse_field_map(*, benchmark_name, source, locator, parser):
    _require_exact_keys(locator, {"kind"}, "locator")
    if locator["kind"] != "field_map":
        raise SourceParserError("field_map parser requires a field_map locator")
    _require_exact_keys(parser, {"kind", "fields"}, "parser")
    fields = parser["fields"]
    if (
        isinstance(fields, (str, bytes, bytearray, Mapping))
        or not isinstance(fields, (list, tuple))
        or not fields
    ):
        raise SourceParserError("field_map fields must be a nonempty ordered sequence")

    normalized_value = {}
    raw_value = {}
    excerpts = {}
    coordinates = {}
    value_coordinates = {}
    value_sha256 = {}
    unit_evidence = {}
    typed_fields = []
    typed_claims = {}
    field_traces = []
    value_spans = {}
    for index, field_spec in enumerate(fields):
        _require_exact_keys(
            field_spec,
            {"locator", "parser"},
            f"field_map fields[{index}]",
        )
        subparser = field_spec["parser"]
        if not isinstance(subparser, Mapping) or subparser.get("kind") == "field_map":
            raise SourceParserError("nested field_map parsers are not supported")
        subtrace = parse_source_target(
            benchmark_name=benchmark_name,
            source=source,
            locator=field_spec["locator"],
            parser=subparser,
        )
        subpayload = subtrace.payload
        subvalues = subpayload["normalized_value"]
        if not isinstance(subvalues, Mapping) or len(subvalues) != 1:
            raise SourceParserError(
                "each field_map child must produce exactly one normalized field"
            )
        field_id = next(iter(subvalues))
        if field_id in normalized_value:
            raise SourceParserError(f"duplicate field_map field {field_id}")
        child_coordinates = subpayload["value_coordinates"]
        span_key = (
            child_coordinates["coordinate_space"],
            child_coordinates["character_start"],
            child_coordinates["character_end"],
        )
        if span_key in value_spans:
            raise SourceParserError(
                "duplicate field_map value span for "
                f"{value_spans[span_key]!r} and {field_id!r}"
            )
        value_spans[span_key] = field_id
        child_fields = subpayload["typed_claim"]["fields"]
        if len(child_fields) != 1 or child_fields[0]["id"] != field_id:
            raise SourceParserError("field_map child typed field mismatch")
        normalized_value[field_id] = subvalues[field_id]
        raw_value[field_id] = subpayload["raw_value"]
        excerpts[field_id] = subpayload["excerpt"]
        coordinates[field_id] = subpayload["coordinates"]
        value_coordinates[field_id] = subpayload["value_coordinates"]
        value_sha256[field_id] = subpayload["value_sha256"]
        unit_evidence[field_id] = subpayload["unit_evidence"]
        typed_fields.append(child_fields[0])
        typed_claims[field_id] = subpayload["typed_claim"]
        field_traces.append(dict(subpayload))

    return ExtractionTrace(
        benchmark_name=benchmark_name,
        payload={
            "schema_version": 1,
            "source_id": source.source_id,
            "source_sha256": source.payload_sha256,
            "extracted_text_sha256": _text_sha256(source.extracted_text),
            "extraction_tool": dict(source.extraction_tool),
            "parser": {
                "id": "field_map",
                "code_sha256": _parser_code_sha256(),
            },
            "locator": dict(locator),
            "coordinates": coordinates,
            "value_coordinates": value_coordinates,
            "value_sha256": value_sha256,
            "unit_evidence": unit_evidence,
            "excerpt": excerpts,
            "excerpt_sha256": {
                field_id: _text_sha256(excerpt)
                for field_id, excerpt in excerpts.items()
            },
            "raw_value": raw_value,
            "raw_value_sha256": value_sha256,
            "normalized_value": normalized_value,
            "typed_claim": {
                "kind": "field_map",
                "fields": typed_fields,
                "claims": typed_claims,
            },
            "field_traces": field_traces,
        },
    )


_LEAF_TARGET_PARSERS = {
    "numeric": _numeric_target,
    "interval": _interval_target,
    "sequence": _collection_target,
    "set": _collection_target,
    "equation": _equation_target,
    "typed_claim": _typed_claim_target,
    "scalar_string": _scalar_string_target,
}


def parse_source_target(*, benchmark_name, source, locator, parser):
    """Extract one runtime target without accepting any expected operand."""

    _require_identifier(benchmark_name, "benchmark_name")
    _validate_verified_source(source)
    if not isinstance(parser, Mapping):
        raise SourceParserError("parser must be a mapping")
    _reject_forbidden_inputs(parser, "parser")
    _reject_forbidden_inputs(locator, "locator")
    parser_kind = parser.get("kind")
    if parser_kind == "field_map":
        if "unit_evidence" in parser:
            raise SourceParserError(
                "field_map unit evidence belongs on each leaf parser"
            )
        return _parse_field_map(
            benchmark_name=benchmark_name,
            source=source,
            locator=locator,
            parser=parser,
        )
    if parser_kind not in SUPPORTED_PARSER_KINDS:
        raise SourceParserError(f"unsupported parser kind {parser.get('kind')!r}")
    target_parser_config = dict(parser)
    unit_contract = target_parser_config.pop("unit_evidence", None)
    source_role_verification = _validate_primary_claim_source(
        source, target_parser_config
    )
    extra_payload = {}
    if parser_kind == "table_numeric":
        (
            start,
            end,
            raw_value,
            normalized_value,
            typed_claim,
            value_span,
            extra_payload,
        ) = _table_numeric_target(source.extracted_text, locator, target_parser_config)
    else:
        start, end, _ = _located_line(source.extracted_text, locator)
        target_function = _LEAF_TARGET_PARSERS[parser_kind]
        raw_value, normalized_value, typed_claim, value_span = target_function(
            source.extracted_text, start, end, target_parser_config
        )
    source_value = source.extracted_text[value_span[0]:value_span[1]]
    if not isinstance(raw_value, str) or raw_value != source_value:
        raise SourceParserError("raw value does not match its exact source span")
    value_sha256 = _text_sha256(source_value)
    unit_evidence = _unit_evidence(
        text=source.extracted_text,
        excerpt_start=start,
        excerpt_end=end,
        value_span=value_span,
        parser_kind=parser_kind,
        parser=target_parser_config,
        locator=locator,
        typed_claim=typed_claim,
        unit_contract=unit_contract,
    )
    return ExtractionTrace(
        benchmark_name=benchmark_name,
        payload={
            "schema_version": 1,
            "source_id": source.source_id,
            "source_sha256": source.payload_sha256,
            "extracted_text_sha256": _text_sha256(source.extracted_text),
            "extraction_tool": dict(source.extraction_tool),
            "parser": {
                "id": parser_kind,
                "code_sha256": _parser_code_sha256(),
            },
            "locator": dict(locator),
            "coordinates": _coordinates(source.extracted_text, start, end),
            "value_coordinates": _coordinates(
                source.extracted_text, value_span[0], value_span[1]
            ),
            "value_sha256": value_sha256,
            "unit_evidence": unit_evidence,
            "excerpt": source.extracted_text[start:end],
            "excerpt_sha256": _text_sha256(source.extracted_text[start:end]),
            "raw_value": raw_value,
            "raw_value_sha256": value_sha256,
            "normalized_value": normalized_value,
            "typed_claim": typed_claim,
            **(
                {"source_role_verification": source_role_verification}
                if source_role_verification is not None
                else {}
            ),
            **extra_payload,
        },
    )
