#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import re
from pathlib import Path

from .agent_fallback import build_agent_inferred


AGENT_BLOCKING_UNSUPPORTED_FEATURES = frozenset(
    {
        "scalar_spin_chirality_terms",
        "three_spin_chirality_terms",
    }
)


def detect_input_kind(source_text: str, source_path: str | None = None) -> dict:
    text = source_text or ""
    if source_path and source_path.endswith(".tex"):
        return {"source_kind": "tex_document"}
    if "\\begin{equation}" in text or "\\section" in text:
        return {"source_kind": "tex_document"}
    if "$" in text or "\\[" in text:
        return {"source_kind": "latex_fragment"}
    return {"source_kind": "natural_language"}


def _default_coordinate_convention() -> dict:
    return {
        "status": "unspecified",
        "frame": "unspecified",
        "axis_labels": [],
        "axis_mapping": {},
        "resolved_frame": None,
        "resolved_axis_labels": [],
        "rotation_matrix": None,
        "family_overrides": {},
        "bond_overrides": {},
        "quantization_axis": None,
        "raw_description": "",
    }


def _selected_coordinate_convention(selection: str) -> dict:
    cleaned = (selection or "").strip()
    if not cleaned:
        return _default_coordinate_convention()

    frame = cleaned
    axis_labels = []
    if cleaned == "global_crystallographic":
        axis_labels = ["a", "b", "c"]
    elif cleaned in {"global_cartesian", "local_bond"}:
        axis_labels = ["x", "y", "z"]

    return {
        "status": "selected",
        "frame": frame,
        "axis_labels": axis_labels,
        "axis_mapping": {},
        "resolved_frame": None,
        "resolved_axis_labels": [],
        "rotation_matrix": None,
        "family_overrides": {},
        "bond_overrides": {},
        "quantization_axis": None,
        "raw_description": "",
    }


def _default_magnetic_order() -> dict:
    return {
        "status": "unspecified",
        "kind": "unspecified",
        "wavevector": [],
        "wavevector_units": None,
        "reference_frame": {
            "kind": "laboratory",
            "phase_origin": None,
        },
        "raw_description": "",
    }


def _parse_numeric_matrix(matrix_body: str) -> list[list[float]] | None:
    rows = []
    for raw_row in re.split(r"\\\\", matrix_body):
        cleaned = raw_row.strip()
        if not cleaned:
            continue
        row = []
        for token in cleaned.split("&"):
            cell = token.strip()
            try:
                row.append(float(cell))
            except ValueError:
                return None
        rows.append(row)
    if len(rows) != 3 or any(len(row) != 3 for row in rows):
        return None
    return rows


def _extract_rotation_matrix(text: str) -> list[list[float]] | None:
    match = re.search(
        r"(?:^|[\s$])R\s*=\s*\\begin\{(?:pmatrix|bmatrix|Bmatrix)\}(?P<body>.*?)\\end\{(?:pmatrix|bmatrix|Bmatrix)\}",
        text,
        flags=re.DOTALL,
    )
    if not match:
        return None
    return _parse_numeric_matrix(match.group("body"))


def _extract_rotation_matrix_from_tabular(text: str) -> tuple[list[str], list[list[float]]] | None:
    for match in re.finditer(
        r"\\begin\{tabular\}\{[^}]*\}(?P<body>.*?)\\end\{tabular\}",
        text,
        flags=re.DOTALL,
    ):
        body = re.sub(r"\\(?:toprule|midrule|bottomrule|hline)", "", match.group("body"))
        rows = []
        for raw_row in re.split(r"\\\\", body):
            cleaned = raw_row.strip()
            if not cleaned:
                continue
            rows.append([_clean_latex_cell(cell) for cell in cleaned.split("&")])
        if len(rows) != 4:
            continue
        header = [cell.strip().lower() for cell in rows[0]]
        if len(header) < 4:
            continue
        column_axes = header[1:4]
        row_axes = [row[0].strip().lower() for row in rows[1:4] if len(row) >= 4]
        if len(row_axes) != 3:
            continue

        def numeric_submatrix(data_rows):
            matrix = []
            for row in data_rows:
                numeric_row = []
                for cell in row[1:4]:
                    value = _parse_numeric_value(cell)
                    if value is None:
                        return None
                    numeric_row.append(value)
                matrix.append(numeric_row)
            return matrix

        if column_axes == ["a", "b", "c"] and row_axes == ["x", "y", "z"]:
            matrix = numeric_submatrix(rows[1:4])
            if matrix is not None:
                return column_axes, matrix

        if column_axes == ["x", "y", "z"] and row_axes == ["a", "b", "c"]:
            matrix = numeric_submatrix(rows[1:4])
            if matrix is not None:
                transposed = [
                    [matrix[col][row] for col in range(3)]
                    for row in range(3)
                ]
                return row_axes, transposed
    return None


def _extract_textual_direction_cosines(text: str, resolved_axis_labels: list[str]) -> list[list[float]] | None:
    rows_by_axis = {}
    lowered = text.lower()
    for match in re.finditer(
        r"(?:local\s+([xyz])\s+axis(?:\s+has\s+direction\s+cosines)?|\\hat\{?([xyz])\}?)\s*=?\s*\(([^)]*)\)",
        lowered,
    ):
        axis = match.group(1) or match.group(2)
        parts = [part.strip() for part in match.group(3).split(",")]
        if len(parts) != 3:
            continue
        try:
            rows_by_axis[axis] = [float(part) for part in parts]
        except ValueError:
            continue
    if all(axis in rows_by_axis for axis in ("x", "y", "z")) and len(resolved_axis_labels) == 3:
        return [rows_by_axis["x"], rows_by_axis["y"], rows_by_axis["z"]]
    return None


def _rotation_matrix_from_axis_mapping(axis_mapping: dict, resolved_axis_labels: list[str]) -> list[list[float]] | None:
    if set(axis_mapping) != {"x", "y", "z"} or len(resolved_axis_labels) != 3:
        return None
    index_by_axis = {axis: idx for idx, axis in enumerate(resolved_axis_labels)}
    matrix = []
    for local_axis in ("x", "y", "z"):
        resolved_axis = axis_mapping.get(local_axis)
        if resolved_axis not in index_by_axis:
            return None
        row = [0.0, 0.0, 0.0]
        row[index_by_axis[resolved_axis]] = 1.0
        matrix.append(row)
    return matrix


def _extract_sections(source_text: str) -> dict:
    sections = {
        "structure_sections": [],
        "model_sections": [],
        "parameter_sections": [],
        "analysis_sections": [],
    }
    current_title = None
    current_lines = []

    def flush_current():
        nonlocal current_title, current_lines
        if current_title is None:
            current_lines = []
            return
        content = "\n".join(current_lines).strip()
        if not content:
            current_lines = []
            return
        lowered = current_title.lower()
        entry = {"title": current_title, "content": content}
        if "structure" in lowered or "crystal" in lowered:
            sections["structure_sections"].append(entry)
        elif "hamiltonian" in lowered or "exchange" in lowered:
            sections["model_sections"].append(entry)
        elif "parameter" in lowered:
            sections["parameter_sections"].append(entry)
        else:
            sections["analysis_sections"].append(entry)
        current_lines = []

    for line in text_lines(source_text):
        title_match = re.match(r"\\section\*\{([^}]*)\}", line.strip())
        if title_match:
            flush_current()
            current_title = title_match.group(1).strip()
            continue
        if current_title is not None:
            current_lines.append(line)

    flush_current()
    return sections


def text_lines(source_text: str) -> list[str]:
    return (source_text or "").splitlines()


def _extract_model_candidates(source_text: str) -> list[dict]:
    candidates = []
    lowered = source_text.lower()
    if "Toy Hamiltonian" in source_text or "toy hamiltonian" in lowered:
        candidates.append({"name": "toy", "role": "simplified", "source_span": "Toy Hamiltonian"})
    if "Effective Hamiltonian" in source_text or "effective hamiltonian" in lowered:
        candidates.append({"name": "effective", "role": "main", "source_span": "Effective Hamiltonian"})
    if "Equivalent Exchange-Matrix Form" in source_text or "equivalent exchange-matrix form" in lowered:
        candidates.append({"name": "matrix_form", "role": "equivalent_form", "source_span": "Equivalent Exchange-Matrix Form"})
    return candidates


def _extract_source_unsupported_features(source_text: str) -> list[str]:
    lowered = (source_text or "").lower()
    features = []
    if "chirality" in lowered and (
        "three-spin" in lowered
        or "three spin" in lowered
        or "scalar spin" in lowered
        or "s_i·(s_j×s_k)" in lowered
        or "s_i.(s_jxs_k)" in lowered
    ):
        features.append("scalar_spin_chirality_terms")
    return features


def _extract_magnetic_order(sections: dict) -> dict:
    snippets = []
    for bucket in ("analysis_sections", "structure_sections", "model_sections"):
        for section in sections.get(bucket, []):
            title = str(section.get("title") or "").strip().lower()
            content = str(section.get("content") or "").strip()
            if not content:
                continue
            lowered = content.lower()
            if "magnetic order" in title or any(
                keyword in lowered
                for keyword in ("single-q", "single q", "spiral", "helical", "propagation vector", "rotating reference frame")
            ):
                snippets.append(content)

    if not snippets:
        return _default_magnetic_order()

    text = "\n\n".join(snippets)
    lowered = text.lower()
    order = _default_magnetic_order()
    order["raw_description"] = text

    if "single-q" in lowered or "single q" in lowered:
        order["status"] = "explicit"
        if "spiral" in lowered:
            order["kind"] = "single_q_spiral"
        elif "helical" in lowered or "helix" in lowered:
            order["kind"] = "single_q_helical"
        else:
            order["kind"] = "single_q_order"

    q_match = re.search(
        r"(?:propagation\s+vector|\\mathbf\s*Q|Q)\s*[:=]?\s*\(?\s*"
        r"(?:\\mathbf\s*Q\s*=\s*)?"
        r"(?:\$\s*)?(?:\\mathbf\s*Q\s*=\s*)?"
        r"\(\s*(?P<x>[-+]?\\frac\{\d+\}\{\d+\}|[-+]?\d+(?:\.\d+)?)\s*,\s*"
        r"(?P<y>[-+]?\\frac\{\d+\}\{\d+\}|[-+]?\d+(?:\.\d+)?)\s*,\s*"
        r"(?P<z>[-+]?\\frac\{\d+\}\{\d+\}|[-+]?\d+(?:\.\d+)?)\s*\)",
        text,
        flags=re.IGNORECASE,
    )
    if q_match:
        def parse_component(component: str) -> float:
            component = component.strip()
            fraction = re.fullmatch(r"(?P<sign>[-+]?)(?:\\frac\{(?P<num>\d+)\}\{(?P<den>\d+)\})", component)
            if fraction:
                value = float(fraction.group("num")) / float(fraction.group("den"))
                return -value if fraction.group("sign") == "-" else value
            return float(component)

        order["status"] = "explicit"
        order["wavevector"] = [
            parse_component(q_match.group("x")),
            parse_component(q_match.group("y")),
            parse_component(q_match.group("z")),
        ]

    if "reciprocal lattice units" in lowered:
        order["wavevector_units"] = "reciprocal_lattice_units"
    elif order["wavevector"] and (
        "(h,k,l)" in lowered
        or "(h, k, l)" in lowered
        or "reciprocal lattice basis" in lowered
        or "reciprocal lattice basis vectors" in lowered
        or "\\mathbf b_1" in text
        or "\\mathbf b_2" in text
        or "\\mathbf b_3" in text
    ):
        order["wavevector_units"] = "reciprocal_lattice_units"
    elif order["wavevector"]:
        order["wavevector_units"] = "unspecified"

    if "rotating reference frame" in lowered or "rotating frame" in lowered:
        order["reference_frame"]["kind"] = "rotating"
        order["status"] = "explicit"
    if "q\\cdot\\mathbf r_n" in lowered or "q\\cdot r_n" in lowered or "q_dot_r" in lowered:
        order["reference_frame"]["phase_origin"] = "Q_dot_r"
    elif "phase" in lowered and order["reference_frame"]["kind"] == "rotating":
        order["reference_frame"]["phase_origin"] = "unspecified"

    return order


def _extract_coordinate_convention_from_text(text: str, *, allow_family_overrides: bool) -> dict:
    if not text.strip():
        return _default_coordinate_convention()

    family_overrides = {}
    bond_overrides = {}
    residual_text = text
    if allow_family_overrides:
        family_matches = list(
            re.finditer(
                r"(?is)\bfor\s+(?:bond\s+)?family\s+(?P<label>[A-Za-z0-9']+)\s*,",
                text,
            )
        )
        if family_matches:
            residual_parts = []
            cursor = 0
            for index, match in enumerate(family_matches):
                residual_parts.append(text[cursor:match.start()])
                body_start = match.end()
                body_end = family_matches[index + 1].start() if index + 1 < len(family_matches) else len(text)
                family_body = text[body_start:body_end].strip()
                family_convention = _extract_coordinate_convention_from_text(
                    family_body,
                    allow_family_overrides=False,
                )
                family_convention["raw_description"] = family_body
                family_overrides[match.group("label")] = family_convention
                cursor = body_end
            residual_parts.append(text[cursor:])
            residual_text = "".join(residual_parts).strip()

        bond_matches = list(
            re.finditer(
                r"(?is)\bfor\s+(?P<label>[A-Za-z0-9_']+)\s+bond\s*,",
                residual_text,
            )
        )
        if bond_matches:
            residual_parts = []
            cursor = 0
            for index, match in enumerate(bond_matches):
                residual_parts.append(residual_text[cursor:match.start()])
                body_start = match.end()
                body_end = bond_matches[index + 1].start() if index + 1 < len(bond_matches) else len(residual_text)
                bond_body = residual_text[body_start:body_end].strip()
                bond_convention = _extract_coordinate_convention_from_text(
                    bond_body,
                    allow_family_overrides=False,
                )
                bond_convention["raw_description"] = bond_body
                bond_overrides[match.group("label")] = bond_convention
                cursor = body_end
            residual_parts.append(residual_text[cursor:])
            residual_text = "".join(residual_parts).strip()

    parse_text = residual_text or text
    lowered = parse_text.lower()
    convention = _default_coordinate_convention()
    convention["raw_description"] = text

    mentions_local_frame = "local bond" in lowered or "local frame" in lowered or "local axes" in lowered
    mentions_global_crystallographic = "global crystallographic" in lowered and re.search(r"\ba\s*,\s*b\s*,\s*c\b", lowered)
    mentions_global_cartesian = (
        ("global" in lowered or "cartesian" in lowered)
        and re.search(r"\bx\s*,\s*y\s*,\s*z\b", lowered)
    )

    if mentions_local_frame:
        convention["status"] = "explicit"
        convention["frame"] = "local_bond"
        convention["axis_labels"] = ["x", "y", "z"]
    elif mentions_global_crystallographic:
        convention["status"] = "explicit"
        convention["frame"] = "global_crystallographic"
        convention["axis_labels"] = ["a", "b", "c"]
    elif mentions_global_cartesian:
        convention["status"] = "explicit"
        convention["frame"] = "global_cartesian"
        convention["axis_labels"] = ["x", "y", "z"]

    if convention["frame"] == "local_bond":
        if mentions_global_crystallographic:
            convention["resolved_frame"] = "global_crystallographic"
            convention["resolved_axis_labels"] = ["a", "b", "c"]
        elif mentions_global_cartesian:
            convention["resolved_frame"] = "global_cartesian"
            convention["resolved_axis_labels"] = ["x", "y", "z"]

    quantization_match = re.search(
        r"(?:local\s+z\s+axis|quantization\s+axis)\s+(?:is\s+)?along\s+([abcxyz])\b",
        lowered,
    )
    if quantization_match:
        convention["status"] = "explicit"
        convention["quantization_axis"] = quantization_match.group(1)

    axis_mapping = {}
    for match in re.finditer(
        r"local\s+([xyz])\s+axis\s+(?:is\s+)?along\s+([abcxyz])\b",
        lowered,
    ):
        axis_mapping[match.group(1)] = match.group(2)
    if axis_mapping:
        convention["status"] = "explicit"
        convention["axis_mapping"] = axis_mapping
        mapped_axes = [axis_mapping.get(axis) for axis in ("x", "y", "z")]
        if all(axis is not None for axis in mapped_axes):
            mapped_set = set(mapped_axes)
            if mapped_set == {"a", "b", "c"}:
                convention["resolved_frame"] = "global_crystallographic"
                convention["resolved_axis_labels"] = ["a", "b", "c"]
            elif mapped_set == {"x", "y", "z"}:
                convention["resolved_frame"] = "global_cartesian"
                convention["resolved_axis_labels"] = ["x", "y", "z"]

    rotation_matrix = _extract_rotation_matrix(parse_text)
    if rotation_matrix is not None:
        convention["status"] = "explicit"
        convention["rotation_matrix"] = rotation_matrix
    else:
        tabular_rotation = _extract_rotation_matrix_from_tabular(parse_text)
        if tabular_rotation is not None:
            resolved_axis_labels, rotation_matrix = tabular_rotation
            convention["status"] = "explicit"
            convention["rotation_matrix"] = rotation_matrix
            convention["resolved_axis_labels"] = list(resolved_axis_labels)
            resolved_set = set(resolved_axis_labels)
            if resolved_set == {"a", "b", "c"}:
                convention["resolved_frame"] = "global_crystallographic"
            elif resolved_set == {"x", "y", "z"}:
                convention["resolved_frame"] = "global_cartesian"

    if convention.get("rotation_matrix") is None:
        textual_rotation = _extract_textual_direction_cosines(
            parse_text,
            list(convention.get("resolved_axis_labels") or []),
        )
        if textual_rotation is not None:
            convention["status"] = "explicit"
            convention["rotation_matrix"] = textual_rotation

    if convention.get("rotation_matrix") is None:
        mapped_rotation = _rotation_matrix_from_axis_mapping(
            dict(convention.get("axis_mapping") or {}),
            list(convention.get("resolved_axis_labels") or []),
        )
        if mapped_rotation is not None:
            convention["status"] = "explicit"
            convention["rotation_matrix"] = mapped_rotation

    if family_overrides:
        convention["family_overrides"] = family_overrides
    if bond_overrides:
        convention["bond_overrides"] = bond_overrides

    return convention


def _extract_coordinate_convention(sections: dict) -> dict:
    snippets = []
    for bucket in ("structure_sections", "model_sections", "analysis_sections"):
        for section in sections.get(bucket, []):
            content = str(section.get("content") or "").strip()
            if not content:
                continue
            lowered = content.lower()
            if any(keyword in lowered for keyword in ("axis", "axes", "coordinate", "frame", "quantization")):
                snippets.append(content)

    if not snippets:
        return _default_coordinate_convention()

    return _extract_coordinate_convention_from_text(
        "\n\n".join(snippets),
        allow_family_overrides=True,
    )


def _selected_candidate_section(sections: dict, candidates: list[dict], selected_name: str | None) -> dict | None:
    if not selected_name:
        primary = [candidate for candidate in candidates if candidate.get("role") in {"main", "simplified"}]
        if len(primary) != 1:
            return None
        selected_name = primary[0]["name"]

    candidate_by_name = {candidate["name"]: candidate for candidate in candidates}
    candidate = candidate_by_name.get(selected_name)
    if not candidate:
        return None

    target_title = str(candidate.get("source_span") or "").strip().lower()
    for section in sections.get("model_sections", []):
        if str(section.get("title") or "").strip().lower() == target_title:
            return section
    return None


def _extract_equation_blocks(section_text: str) -> list[str]:
    blocks = []
    for environment in ("equation", "align", "equation*", "align*"):
        pattern = rf"\\begin\{{{re.escape(environment)}\}}(.*?)\\end\{{{re.escape(environment)}\}}"
        blocks.extend(match.group(1).strip() for match in re.finditer(pattern, section_text, flags=re.DOTALL))
    return [block for block in blocks if block]


def _extract_explicit_local_bond_blocks(equation_blocks: list[str]) -> list[dict]:
    extracted = []
    for block in equation_blocks:
        match = re.match(
            r"\s*(?P<label>[A-Za-z]+_\{[^}]+\}(?:\^\{[^}]+\})?)\s*=",
            block,
            flags=re.DOTALL,
        )
        if not match:
            continue
        label = match.group("label").strip()
        if not re.search(r"_\{[^}]*i[^}]*j[^}]*\}", label):
            continue
        extracted.append({"label": label, "expression": block})
    return extracted


def _select_local_bond_expression(content: str, equation_blocks: list[str]) -> str | None:
    bond_blocks = _extract_explicit_local_bond_blocks(equation_blocks)
    if not bond_blocks:
        return None

    referenced = []
    for entry in bond_blocks:
        if content.count(entry["label"]) > 1:
            referenced.append(entry)

    if len(referenced) == 1:
        return referenced[0]["expression"]
    if len(bond_blocks) == 1 and len(equation_blocks) > 1 and "\\sum_" in content:
        return bond_blocks[0]["expression"]
    return None


def _extract_explicit_local_bond_candidates(content: str, equation_blocks: list[str]) -> list[dict]:
    candidates = []
    for entry in _extract_explicit_local_bond_blocks(equation_blocks):
        family_match = re.search(r"\^\{\((?P<family>[^)]+)\)\}", entry["label"])
        if not family_match:
            continue
        referenced = content.count(entry["label"]) > 1
        if not referenced and not (
            len(_extract_explicit_local_bond_blocks(equation_blocks)) == 1
            and len(equation_blocks) > 1
            and "\\sum_" in content
        ):
            continue
        candidates.append(
            {
                "family": family_match.group("family").strip(),
                "expression": entry["expression"],
            }
        )
    return candidates


def _extract_matrix_exchange_blocks(equation_blocks: list[str]) -> list[dict]:
    extracted = []
    label_pattern = re.compile(
        r"\s*(?P<label>\\mathcal\s*J_\{ij\}\^\{\((?P<family>[^)]+)\)\})\s*=",
        flags=re.DOTALL,
    )
    for block in equation_blocks:
        label_match = label_pattern.match(block)
        if not label_match:
            continue
        matrix_match = re.search(
            r"\\begin\{(?:pmatrix|bmatrix|Bmatrix)\}(?P<body>.*?)\\end\{(?:pmatrix|bmatrix|Bmatrix)\}",
            block,
            flags=re.DOTALL,
        )
        if not matrix_match:
            continue
        extracted.append(
            {
                "label": label_match.group("label").strip(),
                "family": label_match.group("family").strip(),
                "body": matrix_match.group("body").strip(),
            }
        )
    return extracted


def _is_zero_like_token(token: str) -> bool:
    cleaned = str(token).strip().rstrip(".")
    if cleaned in {"0", "+0", "-0"}:
        return True
    try:
        return float(cleaned) == 0.0
    except ValueError:
        return False


def _matrix_block_to_operator_expression(matrix_block: dict) -> str | None:
    rows = []
    for raw_row in re.split(r"\\\\", matrix_block["body"]):
        cleaned = raw_row.strip()
        if not cleaned:
            continue
        rows.append([cell.strip() for cell in cleaned.split("&")])
    if len(rows) != 3 or any(len(row) != 3 for row in rows):
        return None

    axes = ["x", "y", "z"]
    terms = []
    for row_index, row in enumerate(rows):
        for col_index, token in enumerate(row):
            if _is_zero_like_token(token):
                continue
            terms.append(f"{token} * S{axes[row_index]}@0 S{axes[col_index]}@1")
    if not terms:
        return None
    return " + ".join(terms)


def _extract_matrix_exchange_candidates(equation_blocks: list[str]) -> list[dict]:
    candidates = []
    for matrix_block in _extract_matrix_exchange_blocks(equation_blocks):
        expression = _matrix_block_to_operator_expression(matrix_block)
        if expression:
            rows = []
            for raw_row in re.split(r"\\\\", matrix_block["body"]):
                cleaned = raw_row.strip()
                if not cleaned:
                    continue
                rows.append([cell.strip() for cell in cleaned.split("&")])
            candidates.append({"family": matrix_block["family"], "expression": expression, "matrix": rows})
    return candidates


def _matrix_form_needs_coordinate_convention(local_bond_candidates: list[dict]) -> bool:
    for candidate in local_bond_candidates:
        matrix = candidate.get("matrix")
        if not matrix:
            continue
        diagonal = [matrix[i][i] for i in range(3)]
        if diagonal[0] != diagonal[1] or diagonal[1] != diagonal[2]:
            return True
        for row_index in range(3):
            for col_index in range(3):
                if row_index == col_index:
                    continue
                if not _is_zero_like_token(matrix[row_index][col_index]):
                    return True
    return False


def _family_subscript(family_label: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9]+", family_label):
        return "_" + family_label
    return "_{" + family_label + "}"


def _replace_family_index(template: str, index_symbol: str, family_label: str) -> str:
    replaced = re.sub(
        rf"_(?P<index>{re.escape(index_symbol)})(?=\W|$)",
        _family_subscript(family_label),
        template,
    )
    replaced = re.sub(
        rf"\{{{re.escape(index_symbol)}\}}",
        "{" + family_label + "}",
        replaced,
    )
    return replaced


def _extract_coefficient_tokens(expression: str) -> set[str]:
    compact = re.sub(r"\s+", "", expression)
    tokens = set()
    for match in re.finditer(r"(?P<coeff>[A-Za-z0-9_{}^\\.+\-']+)S_i\^zS_j\^z", compact):
        tokens.add(match.group("coeff"))
    ladder_pattern = re.compile(
        r"\\frac\{(?P<coeff>.+?)\}\{2\}\(S_i\^\+S_j\^-"
        r"\+S_i\^-S_j\^\+\)"
    )
    for match in ladder_pattern.finditer(compact):
        tokens.add(match.group("coeff"))
    return tokens


def _is_resolved_token(token: str, parameter_registry: dict) -> bool:
    cleaned = str(token).strip()
    try:
        float(cleaned)
        return True
    except ValueError:
        pass
    if cleaned in parameter_registry:
        return True
    simple_subscript = re.sub(r"_\{([A-Za-z0-9]+)\}", r"_\1", cleaned)
    if simple_subscript in parameter_registry:
        return True
    braced_subscript = re.sub(r"_([A-Za-z0-9]+)(?=\^|$)", r"_{\1}", cleaned)
    return braced_subscript in parameter_registry


def _expand_family_indexed_template(block: str, parameter_registry: dict) -> list[dict]:
    family_match = re.search(
        r"\\sum_\{(?P<index>[A-Za-z])\\in\\\{(?P<families>[^}]*)\\\}\}",
        block,
        flags=re.DOTALL,
    )
    if not family_match:
        return []

    body_match = re.search(r"\\left\[(?P<body>.*?)\\right\]", block, flags=re.DOTALL)
    if not body_match:
        body_match = re.search(r"\[(?P<body>.*?)\]", block, flags=re.DOTALL)
    if not body_match:
        return []

    index_symbol = family_match.group("index").strip()
    families = [item.strip() for item in family_match.group("families").split(",") if item.strip()]
    body = body_match.group("body").strip()
    if not families or not body:
        return []

    candidates = []
    for family in families:
        expression = _replace_family_index(body, index_symbol, family)
        tokens = _extract_coefficient_tokens(expression)
        if tokens and all(_is_resolved_token(token, parameter_registry) for token in tokens):
            candidates.append({"family": family, "expression": expression})
    return candidates


def _extract_family_indexed_candidates(equation_blocks: list[str], parameter_registry: dict) -> list[dict]:
    candidates = []
    for block in equation_blocks:
        candidates.extend(_expand_family_indexed_template(block, parameter_registry))
    return candidates


def _clean_latex_cell(cell: str) -> str:
    text = str(cell).strip()
    if text.startswith("$") and text.endswith("$") and len(text) >= 2:
        text = text[1:-1].strip()
    return text


def _parse_numeric_value(text: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def _parse_direct_numeric_value(text: str) -> float | None:
    raw = str(text)
    match = re.match(r"\s*(?P<value>[-+]?\d+(?:\.\d+)?)", raw)
    if not match:
        return None
    remainder = raw[match.end():].strip()
    if remainder and not (
        remainder.startswith(r"\pm")
        or remainder.startswith("~")
        or remainder.startswith(r"\text")
        or remainder.startswith(r"\mathrm")
        or remainder.startswith(r"\,")
    ):
        return None
    return float(match.group("value"))


def _split_equation_assignments(equation: str) -> list[str]:
    parts = re.split(
        r"\\qquad|,(?=\s*[A-Za-z0-9_{}^\\+\-']+\s*=)",
        str(equation),
    )
    return [part.strip().rstrip(",") for part in parts if part.strip()]


def _read_braced_group(text: str, start: int) -> tuple[str, int]:
    if start >= len(text) or text[start] != "{":
        raise ValueError("expected braced group")
    depth = 0
    index = start
    content_start = start + 1
    while index < len(text):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[content_start:index], index + 1
        index += 1
    raise ValueError("unterminated braced group")


def _expand_latex_fractions(expression: str) -> str:
    text = str(expression or "")
    text = text.replace(r"\tfrac", r"\frac").replace(r"\dfrac", r"\frac")
    result = []
    index = 0
    while index < len(text):
        if text.startswith(r"\frac", index):
            numerator, next_index = _read_braced_group(text, index + len(r"\frac"))
            denominator, next_index = _read_braced_group(text, next_index)
            expanded_num = _expand_latex_fractions(numerator)
            expanded_den = _expand_latex_fractions(denominator)
            result.append(f"(({expanded_num})/({expanded_den}))")
            index = next_index
            continue
        result.append(text[index])
        index += 1
    return "".join(result)


def _is_number_token(token: str) -> bool:
    return re.fullmatch(r"\d+(?:\.\d+)?|\.\d+", str(token or "")) is not None


def _insert_implicit_multiplication(tokens: list[str]) -> list[str]:
    expanded = []
    for token in tokens:
        if expanded:
            prev = expanded[-1]
            prev_is_atom = _is_number_token(prev) or prev == ")" or prev not in {"+", "-", "*", "/", "("}
            next_is_atom = _is_number_token(token) or token == "(" or token not in {"+", "-", "*", "/", ")"}
            if prev_is_atom and next_is_atom:
                expanded.append("*")
        expanded.append(token)
    return expanded


def _tokenize_parameter_expression(expression: str) -> list[str]:
    compact = _expand_latex_fractions(str(expression or ""))
    compact = compact.replace(r"\left", "").replace(r"\right", "")
    compact = compact.replace(r"\cdot", "*").replace(r"\times", "*")
    compact = re.sub(r"\s+", "", compact)
    if not compact:
        return []

    tokens = []
    index = 0
    while index < len(compact):
        char = compact[index]
        if char in "+-*/()":
            tokens.append(char)
            index += 1
            continue
        if char.isdigit() or char == ".":
            match = re.match(r"\d+(?:\.\d+)?|\.\d+", compact[index:])
            if not match:
                return []
            tokens.append(match.group(0))
            index += len(match.group(0))
            continue

        start = index
        depth = 0
        while index < len(compact):
            current = compact[index]
            if current == "{":
                depth += 1
            elif current == "}":
                depth = max(0, depth - 1)
            elif depth == 0 and current in "+-*/()":
                break
            index += 1
        symbol = compact[start:index].strip()
        if symbol:
            tokens.append(symbol)

    return _insert_implicit_multiplication(tokens)


def _resolve_parameter_expression_token(token: str, registry: dict) -> float | None:
    direct_numeric = _parse_direct_numeric_value(token)
    if direct_numeric is not None:
        return direct_numeric
    cleaned = str(token).strip()
    if cleaned in registry:
        return float(registry[cleaned])
    simple_subscript = re.sub(r"_\{([A-Za-z0-9]+)\}", r"_\1", cleaned)
    if simple_subscript in registry:
        return float(registry[simple_subscript])
    braced_subscript = re.sub(r"_([A-Za-z0-9]+)(?=\^|$)", r"_{\1}", cleaned)
    if braced_subscript in registry:
        return float(registry[braced_subscript])
    return None


def _evaluate_parameter_expression(expression: str, registry: dict) -> float | None:
    tokens = _tokenize_parameter_expression(expression)
    if not tokens:
        return None

    def parse_expression(index):
        value, index = parse_term(index)
        while index < len(tokens) and tokens[index] in {"+", "-"}:
            operator = tokens[index]
            rhs, index = parse_term(index + 1)
            value = value + rhs if operator == "+" else value - rhs
        return value, index

    def parse_term(index):
        value, index = parse_factor(index)
        while index < len(tokens) and tokens[index] in {"*", "/"}:
            operator = tokens[index]
            rhs, index = parse_factor(index + 1)
            if operator == "*":
                value *= rhs
            else:
                value /= rhs
        return value, index

    def parse_factor(index):
        if index >= len(tokens):
            raise ValueError("unexpected end of expression")
        token = tokens[index]
        if token == "+":
            return parse_factor(index + 1)
        if token == "-":
            value, next_index = parse_factor(index + 1)
            return -value, next_index
        if token == "(":
            value, next_index = parse_expression(index + 1)
            if next_index >= len(tokens) or tokens[next_index] != ")":
                raise ValueError("missing closing parenthesis")
            return value, next_index + 1
        if _is_number_token(token):
            return float(token), index + 1
        resolved = _resolve_parameter_expression_token(token, registry)
        if resolved is None:
            raise ValueError(f"unresolved token: {token}")
        return resolved, index + 1

    try:
        value, next_index = parse_expression(0)
    except (ValueError, ZeroDivisionError):
        return None
    if next_index != len(tokens):
        return None
    return value


def _extract_parameter_registry(parameter_sections: list[dict]) -> dict:
    registry = {}
    for section in parameter_sections:
        content = str(section.get("content") or "")

        for tabular_match in re.finditer(r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}", content, flags=re.DOTALL):
            tabular_content = re.sub(r"\\(?:toprule|midrule|bottomrule)", "", tabular_match.group(1))
            rows = []
            for raw_row in re.split(r"\\\\", tabular_content):
                cleaned = raw_row.strip()
                if not cleaned:
                    continue
                rows.append([_clean_latex_cell(cell) for cell in cleaned.split("&")])
            if len(rows) < 2:
                continue
            header = rows[0]
            values = rows[1]
            for label, value in zip(header[1:], values[1:]):
                numeric = _parse_numeric_value(value)
                if numeric is not None:
                    registry[label] = numeric

        equation_blocks = []
        for environment in ("equation", "equation*", "align", "align*"):
            pattern = rf"\\begin\{{{re.escape(environment)}\}}(.*?)\\end\{{{re.escape(environment)}\}}"
            equation_blocks.extend(match.group(1).strip() for match in re.finditer(pattern, content, flags=re.DOTALL))

        for equation in equation_blocks:
            normalized_equation = (
                str(equation)
                .replace("&", "")
                .replace(r"\nonumber", "")
                .replace(r"\notag", "")
            )
            for raw_row in re.split(r"\\\\", normalized_equation):
                row = raw_row.strip().rstrip(",")
                if not row:
                    continue
                for assignment in _split_equation_assignments(row):
                    assign_match = re.match(
                        r"(?P<name>[A-Za-z0-9_{}^\\+\-']+)\s*=\s*(?P<value>.+)",
                        assignment,
                        flags=re.DOTALL,
                    )
                    if not assign_match:
                        continue
                    value_text = assign_match.group("value").strip().rstrip(".")
                    numeric = _parse_direct_numeric_value(value_text)
                    if numeric is None:
                        numeric = _evaluate_parameter_expression(value_text, registry)
                    if numeric is not None:
                        registry[assign_match.group("name").strip()] = numeric

    return registry


def _extract_hamiltonian_model(
    sections: dict,
    candidates: list[dict],
    selected_name: str | None,
    parameter_registry: dict,
) -> dict:
    section = _selected_candidate_section(sections, candidates, selected_name)
    if not section:
        return {}

    content = str(section.get("content") or "")
    equation_blocks = _extract_equation_blocks(content)
    if equation_blocks:
        explicit_local_bond_candidates = _extract_explicit_local_bond_candidates(content, equation_blocks)
        matrix_candidates = _extract_matrix_exchange_candidates(equation_blocks)
        if matrix_candidates:
            return {"local_bond_candidates": matrix_candidates, "matrix_form": True}
        family_candidates = _extract_family_indexed_candidates(equation_blocks, parameter_registry)
        if explicit_local_bond_candidates and family_candidates:
            combined = explicit_local_bond_candidates + family_candidates
            combined.sort(key=lambda entry: entry["family"])
            return {"local_bond_candidates": combined}
        if family_candidates:
            return {"local_bond_candidates": family_candidates}
        if explicit_local_bond_candidates:
            return {"local_bond_candidates": explicit_local_bond_candidates}
        local_bond_expression = _select_local_bond_expression(content, equation_blocks)
        if local_bond_expression:
            return {"operator_expression": local_bond_expression}
        return {"operator_expression": "\n\n".join(equation_blocks)}
    if content.strip():
        return {"operator_expression": content.strip()}
    return {}


def _operator_expression_unsupported_features(expression: str) -> list[str]:
    compact = re.sub(r"\s+", "", str(expression or ""))
    features = []
    if "\\gamma_{ij}" in compact or "\\gamma_{ij}^\\ast" in compact:
        features.append("bond_dependent_phase_gamma_terms")
    if "^{\\pm\\pm}" in compact or "S_i^+S_j^+" in compact or "S_i^-S_j^-" in compact:
        features.append("double_raising_lowering_exchange_terms")
    if "^{z\\pm}" in compact or re.search(r"(S_i\^[\+\-]S_j\^z|S_i\^zS_j\^[\+\-])", compact):
        features.append("zpm_offdiagonal_exchange_terms")
    return features


def _extend_unsupported_features(record: dict, expression: str) -> list[str]:
    combined = list(record.get("unsupported_features", []))
    for feature in _operator_expression_unsupported_features(expression):
        if feature not in combined:
            combined.append(feature)
    return combined


def build_intermediate_record(
    source_text: str,
    source_path: str | None = None,
    selected_model_candidate: str | None = None,
    selected_local_bond_family: str | None = None,
    selected_coordinate_convention: str | None = None,
) -> dict:
    kind = detect_input_kind(source_text, source_path=source_path)
    sections = _extract_sections(source_text)
    candidates = _extract_model_candidates(source_text)
    ambiguities = []
    unsupported_features = _extract_source_unsupported_features(source_text)

    blocking_candidates = [candidate for candidate in candidates if candidate["role"] in {"main", "simplified"}]
    selected_name = (selected_model_candidate or "").strip() or None
    selected_is_valid = selected_name in {candidate["name"] for candidate in candidates}
    if len(blocking_candidates) > 1 and not selected_is_valid:
        ambiguities.append(
            {
                "id": "model_candidate_selection",
                "blocks_landing": True,
                "question": "Multiple Hamiltonian candidates were detected. Which one should I use?",
            }
        )

    hamiltonian_model = {}
    parameter_registry = {}
    if not ambiguities:
        parameter_registry = _extract_parameter_registry(
            list(sections.get("parameter_sections", [])) + list(sections.get("model_sections", []))
        )
        hamiltonian_model = _extract_hamiltonian_model(sections, candidates, selected_name, parameter_registry)

    return {
        "source_document": {
            "source_kind": kind["source_kind"],
            "source_path": source_path,
        },
        "source_text": source_text,
        "document_sections": sections,
        "model_candidates": candidates,
        "selected_model_candidate": selected_name,
        "selected_local_bond_family": (selected_local_bond_family or "").strip() or None,
        "selected_coordinate_convention": (selected_coordinate_convention or "").strip() or None,
        "system_context": {
            "coordinate_convention": (
                _selected_coordinate_convention(selected_coordinate_convention)
                if (selected_coordinate_convention or "").strip()
                else _extract_coordinate_convention(sections)
            ),
            "magnetic_order": _extract_magnetic_order(sections),
        },
        "lattice_model": {},
        "hamiltonian_model": hamiltonian_model,
        "parameter_registry": parameter_registry,
        "ambiguities": ambiguities,
        "confidence_report": {},
        "unsupported_features": unsupported_features,
    }


def _agent_fallback_proposal(record: dict) -> dict:
    proposal = build_agent_inferred(
        source_text=record.get("source_text", ""),
        intermediate_record=record,
        normalization_context={
            "selected_coordinate_convention": record.get("selected_coordinate_convention"),
            "selected_local_bond_family": record.get("selected_local_bond_family"),
        },
    )
    proposed = deepcopy(proposal)
    blocking_unsupported = [
        feature
        for feature in list(record.get("unsupported_features", []))
        if feature in AGENT_BLOCKING_UNSUPPORTED_FEATURES
    ]
    if blocking_unsupported:
        proposed["landing_readiness"] = "unsupported_even_with_agent"
        agent_inferred = proposed.setdefault("agent_inferred", {})
        agent_inferred["unsupported_even_with_agent"] = blocking_unsupported
        user_explanation = agent_inferred.setdefault("user_explanation", {})
        user_explanation["summary"] = (
            "The helper recognized unsupported interaction terms that still need "
            "manual handling before the input can land."
        )
    agent_inferred = proposed.setdefault("agent_inferred", {})
    inferred_fields = agent_inferred.setdefault("inferred_fields", {})
    unresolved_items = agent_inferred.setdefault("unresolved_items", [])
    if inferred_fields.get("structure_file") and not inferred_fields.get("hamiltonian_file"):
        unresolved_items.append(
            {
                "field": "hamiltonian_file",
                "reason": (
                    "I found a structure file path, but not a matching hr-style "
                    "Hamiltonian file path. Which hr file should I use?"
                ),
                "policy": "needs_unique_interpretation",
            }
        )
    if inferred_fields.get("hamiltonian_file") and not inferred_fields.get("structure_file"):
        unresolved_items.append(
            {
                "field": "structure_file",
                "reason": (
                    "I found an hr-style Hamiltonian file path, but not a matching "
                    "structure file path. Which structure file should I use?"
                ),
                "policy": "needs_unique_interpretation",
            }
        )
    if unresolved_items and proposed.get("landing_readiness") == "agent_proposed_ok":
        proposed["landing_readiness"] = "agent_proposed_needs_input"
    return proposed


def _document_landing_readiness(proposal: dict) -> str:
    if (proposal or {}).get("landing_readiness") == "unsupported_even_with_agent":
        return "unsupported_even_with_agent"
    return "agent_proposed_needs_input"


def _is_vague_dialogue(source_text: str) -> bool:
    lowered = (source_text or "").lower()
    return any(
        marker in lowered
        for marker in (
            "maybe",
            "something like",
            "some ",
            "kind of",
            "sort of",
            "not sure",
        )
    )


def _should_surface_agent_fallback(record: dict, proposal: dict) -> bool:
    agent_inferred = (proposal or {}).get("agent_inferred", {})
    return bool(
        agent_inferred.get("inferred_fields")
        or agent_inferred.get("unresolved_items")
        or record.get("unsupported_features")
        or (
            agent_inferred.get("status") == "rejected"
            and _is_vague_dialogue(record.get("source_text", ""))
        )
    )


def _interaction_from_agent_fallback(proposal: dict) -> dict | None:
    landing_readiness = (proposal or {}).get("landing_readiness")
    agent_inferred = (proposal or {}).get("agent_inferred", {})
    summary = (
        ((agent_inferred.get("user_explanation") or {}).get("summary"))
        or "I need a bit more input before I can land this safely."
    )
    if landing_readiness == "unsupported_even_with_agent":
        return {
            "status": "needs_input",
            "id": "unsupported_features_review",
            "question": summary,
        }

    unresolved_items = list(agent_inferred.get("unresolved_items", []))
    if unresolved_items:
        first = unresolved_items[0]
        field = first.get("field")
        interaction_id = {
            "coordinate_convention": "coordinate_convention_selection",
            "model_candidate": "model_candidate_selection",
            "structure_file": "structure_file_selection",
            "hamiltonian_file": "hamiltonian_hr_file_selection",
        }.get(field, "agent_fallback_review")
        return {
            "status": "needs_input",
            "id": interaction_id,
            "question": first.get("reason") or summary,
        }

    if agent_inferred.get("status") != "proposed":
        return {
            "status": "needs_input",
            "id": "agent_fallback_review",
            "question": summary,
        }
    return None


def land_intermediate_record(record: dict) -> dict:
    blocking = [entry for entry in record.get("ambiguities", []) if entry.get("blocks_landing")]
    if blocking:
        question = blocking[0]
        landed = {
            "interaction": {
                "status": "needs_input",
                "id": question["id"],
                "question": question["question"],
            },
            "magnetic_order": dict(record.get("system_context", {}).get("magnetic_order", {})),
            "unsupported_features": list(record.get("unsupported_features", [])),
        }
        if record.get("source_document", {}).get("source_kind") == "natural_language":
            proposal = _agent_fallback_proposal(record)
            if _should_surface_agent_fallback(record, proposal):
                landed["landing_readiness"] = _document_landing_readiness(proposal)
                landed["agent_inferred"] = deepcopy(proposal.get("agent_inferred", {}))
        return landed

    hamiltonian_model = record.get("hamiltonian_model", {})
    coordinate_convention = dict(record.get("system_context", {}).get("coordinate_convention", {}))
    magnetic_order = dict(record.get("system_context", {}).get("magnetic_order", {}))
    if (
        record.get("selected_model_candidate") == "matrix_form"
        and hamiltonian_model.get("matrix_form")
        and coordinate_convention.get("status") == "unspecified"
        and _matrix_form_needs_coordinate_convention(list(hamiltonian_model.get("local_bond_candidates", [])))
    ):
        return {
            "interaction": {
                "status": "needs_input",
                "id": "coordinate_convention_selection",
                "question": (
                    "The selected exchange-matrix form contains anisotropic tensor components, "
                    "but the coordinate convention is not specified. Which coordinate frame should I use?"
                ),
                "options": ["global_crystallographic", "global_cartesian", "local_bond"],
            },
            "coordinate_convention": coordinate_convention,
            "magnetic_order": magnetic_order,
            "unsupported_features": list(record.get("unsupported_features", [])),
        }

    local_bond_candidates = list(hamiltonian_model.get("local_bond_candidates", []))
    if local_bond_candidates:
        selected_family = record.get("selected_local_bond_family")
        by_family = {entry["family"]: entry for entry in local_bond_candidates}
        if selected_family == "all":
            combined_unsupported = list(record.get("unsupported_features", []))
            for entry in local_bond_candidates:
                for feature in _operator_expression_unsupported_features(entry.get("expression", "")):
                    if feature not in combined_unsupported:
                        combined_unsupported.append(feature)
            return {
                "representation": "operator_family_collection",
                "support": [0, 1],
                "expressions": [
                    {"family": entry["family"], "expression": entry["expression"]}
                    for entry in local_bond_candidates
                ],
                "parameters": dict(record.get("parameter_registry", {})),
                "coordinate_convention": coordinate_convention,
                "magnetic_order": magnetic_order,
                "user_notes": "Generated from document input protocol",
                "unsupported_features": combined_unsupported,
            }
        if selected_family and selected_family in by_family:
            expression = by_family[selected_family]["expression"]
        elif len(local_bond_candidates) == 1:
            expression = local_bond_candidates[0]["expression"]
        else:
            return {
                "interaction": {
                    "status": "needs_input",
                    "id": "local_bond_family_selection",
                    "question": "Multiple local bond families were derived from the effective Hamiltonian. Which family should I use?",
                    "options": [entry["family"] for entry in local_bond_candidates],
                },
                "magnetic_order": magnetic_order,
                "unsupported_features": list(record.get("unsupported_features", [])),
            }
    else:
        expression = (
            hamiltonian_model.get("operator_expression")
            or hamiltonian_model.get("value")
            or ""
        )
    if (
        record.get("source_document", {}).get("source_kind") == "natural_language"
        and not local_bond_candidates
        and not str(expression).strip()
    ):
        proposal = _agent_fallback_proposal(record)
        if _should_surface_agent_fallback(record, proposal):
            landed = {
                "landing_readiness": _document_landing_readiness(proposal),
                "agent_inferred": deepcopy(proposal.get("agent_inferred", {})),
                "coordinate_convention": coordinate_convention,
                "magnetic_order": magnetic_order,
                "unsupported_features": list(record.get("unsupported_features", [])),
            }
            interaction = _interaction_from_agent_fallback(proposal)
            if interaction is not None:
                landed["interaction"] = interaction
            return landed
    return {
        "representation": "operator",
        "support": [0, 1],
        "expression": expression,
        "parameters": dict(record.get("parameter_registry", {})),
        "coordinate_convention": coordinate_convention,
        "magnetic_order": magnetic_order,
        "user_notes": "Generated from document input protocol",
        "unsupported_features": _extend_unsupported_features(record, expression),
    }


def load_source_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")
