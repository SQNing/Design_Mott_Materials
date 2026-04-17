#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


def _format_value(value):
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _summary_parts(summary):
    text = str(summary or "").strip()
    if not text:
        return None, None
    parts = [part.strip() for part in text.split(". ") if part.strip()]
    if not parts:
        return text, None
    overview = parts[0]
    if not overview.endswith("."):
        overview += "."
    if len(parts) == 1:
        return overview, None
    interpretation = ". ".join(part.rstrip(".") for part in parts[1:]) + "."
    return overview, interpretation


def _context_lines(payload):
    normalized = payload.get("normalized_model", {}) if isinstance(payload, dict) else {}
    if not isinstance(normalized, dict):
        return []
    lines = []
    model_candidate = normalized.get("selected_model_candidate")
    local_bond_family = normalized.get("selected_local_bond_family")
    coordinate_convention = normalized.get("selected_coordinate_convention")
    provenance = normalized.get("provenance", {}) if isinstance(normalized.get("provenance"), dict) else {}
    source_mode = provenance.get("source_mode")
    if model_candidate:
        lines.append(f"- model candidate: `{model_candidate}`")
    if local_bond_family:
        lines.append(f"- local bond family: `{local_bond_family}`")
    if coordinate_convention:
        lines.append(f"- coordinate convention: `{coordinate_convention}`")
    if source_mode:
        lines.append(f"- source mode: `{source_mode}`")
    return lines


def _notes_lines(payload, main_blocks):
    normalized = payload.get("normalized_model", {}) if isinstance(payload, dict) else {}
    if not isinstance(normalized, dict):
        normalized = {}
    lines = []
    system = normalized.get("system", {}) if isinstance(normalized.get("system"), dict) else {}
    units = system.get("units")
    if units:
        if units == "unspecified":
            lines.append("- coefficient units: `unspecified` (no explicit energy unit detected in source)")
        else:
            lines.append(f"- coefficient units: `{units}`")

    first_block = main_blocks[0] if main_blocks else {}
    if not isinstance(first_block, dict):
        return lines

    matrix_axes = list(first_block.get("matrix_axes") or first_block.get("axis_labels") or [])
    if first_block.get("type") in {"symmetric_exchange_matrix", "exchange_tensor"}:
        if matrix_axes:
            lines.append(f"- reported matrix basis: `({', '.join(matrix_axes)})`")
        else:
            lines.append("- matrix basis: default operator basis `(x, y, z)`")
    elif first_block.get("type") == "xxz_exchange":
        axis_labels = list(first_block.get("axis_labels") or [])
        planar_axes = list(first_block.get("planar_axes") or [])
        longitudinal_axis = first_block.get("longitudinal_axis")
        if axis_labels:
            lines.append(f"- reported axis basis: `({', '.join(axis_labels)})`")
        if planar_axes or longitudinal_axis:
            planar_text = f"({', '.join(planar_axes)})" if planar_axes else "(unspecified)"
            longitudinal_text = longitudinal_axis if longitudinal_axis else "unspecified"
            lines.append(
                f"- planar axes: `{planar_text}`; longitudinal axis: `{longitudinal_text}`"
            )
    return lines


def _markdown_table_lines(rows):
    widths = [0] * len(rows[0])
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))

    def _format_row(row):
        padded = [str(cell).ljust(widths[index]) for index, cell in enumerate(row)]
        return "| " + " | ".join(padded) + " |"

    separator = "| " + " | ".join("-" * width for width in widths) + " |"
    return [
        _format_row(rows[0]),
        separator,
        *(_format_row(row) for row in rows[1:]),
    ]


def _parameter_lines(block):
    entries = list(block.get("human_parameters") or [])
    if not entries:
        return []
    rows = [["Name", "Kind", "Value"]]
    for entry in entries:
        rows.append(
            [entry.get("name"), entry.get("kind"), _format_value(entry.get("value"))]
        )
    return _markdown_table_lines(rows)


def _matrix_lines(block):
    matrix = block.get("matrix")
    if not isinstance(matrix, list):
        return []
    if len(matrix) != 3 or any(not isinstance(row, list) or len(row) != 3 for row in matrix):
        return [
            "```text",
            json.dumps(matrix),
            "```",
        ]
    axes = list(block.get("matrix_axes") or block.get("axis_labels") or ["x", "y", "z"])
    if len(axes) != 3:
        axes = ["x", "y", "z"]
    rows = [["", axes[0], axes[1], axes[2]]]
    for axis, row in zip(axes, matrix):
        rows.append(
            [axis, _format_value(row[0]), _format_value(row[1]), _format_value(row[2])]
        )
    return _markdown_table_lines(rows)


def _residual_term_lines(terms):
    entries = list(terms or [])
    if not entries:
        return []
    rows = [["Label", "Family", "Rank", "Body", "Coefficient"]]
    for entry in entries:
        rows.append(
            [
                entry.get("canonical_label", ""),
                entry.get("multipole_family", entry.get("family", "unspecified")),
                entry.get("multipole_rank", ""),
                entry.get("body_order", ""),
                _format_value(entry.get("coefficient")),
            ]
        )
    return _markdown_table_lines(rows)


def _residual_summary_lines(entries):
    rows = [["Family", "Rank", "Body", "Count", "Max abs(coeff)"]]
    for entry in list(entries or []):
        rows.append(
            [
                entry.get("multipole_family", "unspecified"),
                entry.get("multipole_rank", ""),
                entry.get("body_order", ""),
                entry.get("term_count", ""),
                _format_value(entry.get("max_abs_coefficient")),
            ]
        )
    if len(rows) == 1:
        return []
    return _markdown_table_lines(rows)


def _shell_physical_summary_sections(main_blocks):
    grouped = {}
    order = []
    for block in list(main_blocks or []):
        if block.get("type") != "shell_resolved_exchange":
            continue
        for shell in list(block.get("shells") or []):
            view = shell.get("physical_parameter_view") or {}
            if not isinstance(view, dict):
                continue
            view_kind = view.get("view_kind")
            parameters = list(view.get("parameters") or [])
            if not view_kind or not parameters:
                continue
            if view_kind not in grouped:
                grouped[view_kind] = {
                    "label": view.get("physical_label") or shell.get("physical_label") or view_kind,
                    "parameter_names": [entry.get("name") for entry in parameters],
                    "rows": [],
                }
                order.append(view_kind)
            value_map = {entry.get("name"): _format_value(entry.get("value")) for entry in parameters}
            grouped[view_kind]["rows"].append(
                [str(shell.get("family", ""))] + [value_map.get(name, "") for name in grouped[view_kind]["parameter_names"]]
            )

    sections = []
    for view_kind in order:
        group = grouped[view_kind]
        rows = [["Family", *group["parameter_names"]], *group["rows"]]
        sections.append(
            {
                "label": group["label"],
                "table_lines": _markdown_table_lines(rows),
            }
        )
    return sections


def render_simplified_model_report(payload, title="Simplified Model Report"):
    lines = [
        f"# {title}",
        "",
        "## Status",
        "",
        f"- status: `{payload.get('status')}`",
        f"- stage: `{payload.get('stage')}`",
    ]

    unsupported = list(payload.get("unsupported_features") or [])
    if unsupported:
        lines.append(f"- unsupported_features: `{unsupported}`")

    context_lines = _context_lines(payload)
    if context_lines:
        lines.extend(["", "## Context", "", *context_lines])

    main_blocks = list((payload.get("effective_model") or {}).get("main") or [])
    residual_summary = list((payload.get("effective_model") or {}).get("residual_summary") or [])
    residual_terms = list((payload.get("effective_model") or {}).get("residual") or [])
    low_weight_summary = list((payload.get("effective_model") or {}).get("low_weight_summary") or [])
    low_weight_terms = list((payload.get("effective_model") or {}).get("low_weight") or [])

    notes_lines = _notes_lines(payload, main_blocks)
    if notes_lines:
        lines.extend(["", "## Notes", "", *notes_lines])

    if not main_blocks:
        lines.extend(["", "## Main Blocks", "", "- none"])
    else:
        lines.extend(["", "## Main Blocks", ""])
        for index, block in enumerate(main_blocks, start=1):
            lines.append(f"### Block {index}")
            lines.append("")
            lines.append(f"- type: `{block.get('type')}`")
            if block.get("physical_label"):
                lines.append(f"- physical label: `{block.get('physical_label')}`")
            aliases = list(block.get("physical_label_aliases") or [])
            if aliases:
                lines.append(f"- physical label aliases: `{', '.join(aliases)}`")
            if block.get("physical_tendency"):
                lines.append(f"- physical tendency: `{block.get('physical_tendency')}`")
            if block.get("dominant_channel_label"):
                lines.append(f"- dominant channel: `{block.get('dominant_channel_label')}`")
            summary = block.get("human_summary")
            if summary:
                overview, interpretation = _summary_parts(summary)
                if overview:
                    lines.append(f"- overview: {overview}")
                if interpretation:
                    lines.append(f"- interpretation: {interpretation}")
            parameter_lines = _parameter_lines(block)
            if parameter_lines:
                lines.append("- key parameters:")
                lines.extend(parameter_lines)
            matrix_lines = _matrix_lines(block)
            if matrix_lines:
                lines.append("- matrix:")
                lines.extend(matrix_lines)
            lines.append("")

    shell_sections = _shell_physical_summary_sections(main_blocks)
    if shell_sections:
        lines.extend(["", "## Shell-Resolved Physical Summary", ""])
        for section in shell_sections:
            lines.append(f"### {section['label']}")
            lines.append("")
            lines.extend(section["table_lines"])
            lines.append("")

    residual_summary_lines = _residual_summary_lines(residual_summary)
    if residual_summary_lines:
        lines.extend(
            [
                "",
                "## Residual Summary",
                "",
                "- Grouped view of residual multipole content by family, rank, and body order.",
                *residual_summary_lines,
            ]
        )

    residual_lines = _residual_term_lines(residual_terms)
    if residual_lines:
        lines.extend(
            [
                "",
                "## Residual Terms",
                "",
                "- These terms were kept exactly but do not yet match a named readable template.",
                *residual_lines,
            ]
        )

    low_weight_summary_lines = _residual_summary_lines(low_weight_summary)
    if low_weight_summary_lines:
        lines.extend(
            [
                "",
                "## Low-Weight Summary",
                "",
                "- Grouped view of low-weight multipole content by family, rank, and body order.",
                *low_weight_summary_lines,
            ]
        )

    low_weight_lines = _residual_term_lines(low_weight_terms)
    if low_weight_lines:
        lines.extend(
            [
                "",
                "## Low-Weight Terms",
                "",
                "- These terms were retained with smaller relative weight.",
                *low_weight_lines,
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--title", default="Simplified Model Report")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    markdown = render_simplified_model_report(payload, title=str(args.title))
    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
